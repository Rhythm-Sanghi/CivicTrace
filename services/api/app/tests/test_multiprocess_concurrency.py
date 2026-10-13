import os
import tempfile
import multiprocessing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.entities import Base, Report, IssueCategory
from app.core.sequences import (
    allocate_report_public_id,
    allocate_case_event_index,
)


def _worker_allocate_reports(db_path: str, count: int, return_queue):
    """Worker executed in an independent operating system process."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"timeout": 30.0},
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    allocated = []
    try:
        for _ in range(count):
            rid = allocate_report_public_id(session, year=2026)
            session.commit()
            allocated.append(rid)
        return_queue.put(("SUCCESS", allocated))
    except Exception as e:
        return_queue.put(("ERROR", str(e)))
    finally:
        session.close()
        engine.dispose()


def _worker_allocate_case_events(db_path: str, case_id: str, count: int, return_queue):
    """Worker executed in an independent OS process for per-case event index allocation."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"timeout": 30.0},
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    indices = []
    try:
        for _ in range(count):
            idx = allocate_case_event_index(session, case_id)
            session.commit()
            indices.append(idx)
        return_queue.put(("SUCCESS", indices))
    except Exception as e:
        return_queue.put(("ERROR", str(e)))
    finally:
        session.close()
        engine.dispose()


def test_multiprocess_report_id_concurrency():
    """
    Spawns multiple separate OS processes simultaneously requesting report IDs
    against an independent database. Verifies database-enforced monotonic uniqueness.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(bind=engine)
        engine.dispose()

        num_processes = 4
        ids_per_process = 10
        total_expected = num_processes * ids_per_process

        queue = multiprocessing.Queue()
        processes = [
            multiprocessing.Process(
                target=_worker_allocate_reports,
                args=(db_path, ids_per_process, queue),
            )
            for _ in range(num_processes)
        ]

        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=15)

        all_ids = []
        for _ in range(num_processes):
            status, res = queue.get(timeout=5)
            assert status == "SUCCESS", f"Worker failed: {res}"
            all_ids.extend(res)

        assert len(all_ids) == total_expected
        assert len(set(all_ids)) == total_expected, (
            "Collision detected in multi-process sequence allocation!"
        )

        numbers = sorted([int(x.split("-")[-1]) for x in all_ids])
        assert numbers == list(range(1, total_expected + 1)), (
            f"Gaps or non-monotonic values: {numbers}"
        )

        # Test no reuse after deletion
        test_engine = create_engine(f"sqlite:///{db_path}")
        TestSession = sessionmaker(bind=test_engine)
        s = TestSession()
        cat = IssueCategory(name="Temp Cat", code="TMP1", default_severity_weight=1.0)
        s.add(cat)
        s.flush()

        # Insert a report with the latest ID
        rep = Report(
            public_id=all_ids[-1],
            category_id=cat.id,
            title="Test",
            description="Test",
            latitude=0.0,
            longitude=0.0,
        )
        s.add(rep)
        s.commit()

        # Delete the report
        s.delete(rep)
        s.commit()

        # Next allocation must NEVER reuse the deleted report's ID
        next_id = allocate_report_public_id(s, year=2026)
        s.commit()
        next_num = int(next_id.split("-")[-1])
        assert next_num == total_expected + 1, (
            f"Deleted ID was reused: got {next_num}, expected {total_expected + 1}"
        )

        s.close()
        test_engine.dispose()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass


def test_multiprocess_per_case_event_index_concurrency():
    """
    Verifies that separate OS processes concurrently allocating event indices
    for the same case receive unique, monotonic indices without conflict.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(bind=engine)
        engine.dispose()

        case_id = "test-case-uuid-12345"
        num_processes = 4
        indices_per_process = 8
        total_expected = num_processes * indices_per_process

        queue = multiprocessing.Queue()
        processes = [
            multiprocessing.Process(
                target=_worker_allocate_case_events,
                args=(db_path, case_id, indices_per_process, queue),
            )
            for _ in range(num_processes)
        ]

        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=15)

        all_indices = []
        for _ in range(num_processes):
            status, res = queue.get(timeout=5)
            assert status == "SUCCESS", f"Worker failed: {res}"
            all_indices.extend(res)

        assert len(all_indices) == total_expected
        assert len(set(all_indices)) == total_expected, (
            "Collision in case event indices across processes!"
        )
        assert sorted(all_indices) == list(range(1, total_expected + 1))
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
