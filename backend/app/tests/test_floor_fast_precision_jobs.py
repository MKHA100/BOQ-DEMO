def test_precision_job_is_registered(foundation_db):
    import app.jobs.worker as worker
    worker._register_processors()
    assert "rooms.precision_refine" in worker.PROCESSORS
    assert "rooms.interpret_ambiguous" in worker.PROCESSORS
