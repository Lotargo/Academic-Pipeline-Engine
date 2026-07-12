import asyncio
import sys

from academic_pe.evaluation import run_routing_benchmark
from academic_pe.routing import ProviderInfrastructureConfig, QdrantRoutingIndex


async def main() -> None:
    if "--qdrant" not in sys.argv:
        print((await run_routing_benchmark()).model_dump_json(indent=2))
        return
    configuration = ProviderInfrastructureConfig.from_yaml()
    index = QdrantRoutingIndex.from_provider_config(configuration)
    try:
        print((await run_routing_benchmark(index=index)).model_dump_json(indent=2))
    finally:
        await index.aclose()


if __name__ == "__main__":
    asyncio.run(main())
