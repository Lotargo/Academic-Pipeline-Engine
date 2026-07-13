from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_root_compose_is_the_canonical_service_dev_entrypoint():
    root_compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    expected_services = {
        "broker",
        "migrate",
        "backend",
        "worker-generation",
        "worker-export",
        "worker-maintenance",
        "scheduler",
        "frontend",
    }

    assert root_compose["name"] == "academic-pipeline-engine-service-dev"
    assert set(root_compose["services"]) == expected_services
    assert all(
        service["extends"] == {
            "file": "docker-compose.service-dev.yml",
            "service": name,
        }
        for name, service in root_compose["services"].items()
    )


def test_service_dev_process_matrix_separates_broker_workers_and_export_image():
    compose = yaml.safe_load((ROOT / "docker-compose.service-dev.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["broker"]["image"] == "rabbitmq:4.3.2-management-alpine"
    assert services["broker"]["healthcheck"]["test"] == ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
    assert "./docker/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro" in services["broker"]["volumes"]

    for service_name in ("migrate", "backend", "worker-generation", "worker-maintenance", "scheduler"):
        service = services[service_name]
        assert service["image"] == "ape-service-dev-api:local"
        assert service["build"]["target"] == "api"

    generation = services["worker-generation"]
    assert generation["build"]["target"] == "api"
    assert "generation,research" in generation["command"][-1]
    assert "broker" in generation["depends_on"]

    export = services["worker-export"]
    assert export["build"]["target"] == "export"
    assert export["command"][-1] == "--queues=export"
    assert "soffice --headless --version" in export["healthcheck"]["test"][-1]

    assert services["worker-maintenance"]["command"][-1] == "--queues=maintenance"
    assert services["scheduler"]["command"][3] == "beat"
    assert services["scheduler"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert services["scheduler"]["healthcheck"]["test"] == ["CMD", "python", "scripts/healthcheck_celery_beat.py"]
    assert services["frontend"]["environment"]["APE_PUBLIC_APP_ORIGIN"] == "http://localhost:3000"

    rabbitmq_config = (ROOT / "docker" / "rabbitmq.conf").read_text(encoding="utf-8")
    assert "deprecated_features.permit.transient_nonexcl_queues = true" in rabbitmq_config
    assert "deprecated_features.permit.global_qos = true" in rabbitmq_config


def test_api_and_export_stages_keep_libreoffice_out_of_shared_backend_image():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    api_stage = dockerfile.split("FROM backend-base AS api", 1)[1].split("FROM backend-base AS export", 1)[0]
    export_stage = dockerfile.split("FROM backend-base AS export", 1)[1]
    base_stage = dockerfile.split("FROM backend-base AS api", 1)[0]
    assert "libreoffice" not in api_stage
    assert "libreoffice-core libreoffice-writer" in export_stage
    assert 'USER ape' in base_stage
    assert 'USER root' in export_stage and export_stage.count('USER ape') == 1
