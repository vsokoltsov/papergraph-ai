import app.ingestion.run as run


def test_push_ingestion_metrics_pushes_to_gateway(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(
        run,
        "push_metrics_to_gateway",
        lambda gateway_url, job: calls.append((gateway_url, job)),
    )

    run.push_ingestion_metrics("http://pushgateway:9091")

    assert calls == [("http://pushgateway:9091", "papergraph-ingestion")]


def test_push_ingestion_metrics_does_not_fail_when_gateway_is_down(
    monkeypatch,
    capsys,
) -> None:
    def fail_push_metrics_to_gateway(gateway_url: str, job: str) -> None:
        raise ConnectionError("cannot connect")

    monkeypatch.setattr(run, "push_metrics_to_gateway", fail_push_metrics_to_gateway)

    run.push_ingestion_metrics("http://pushgateway:9091")

    assert "Could not push Prometheus metrics: cannot connect" in capsys.readouterr().out
