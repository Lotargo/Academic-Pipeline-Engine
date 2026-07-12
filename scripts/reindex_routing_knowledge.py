import asyncio

from academic_pe.routing import ProviderInfrastructureConfig, QdrantRoutingIndex
from academic_pe.routing.projection import reindex_canonical_routing_cards


async def main() -> None:
    configuration = ProviderInfrastructureConfig.from_yaml()
    index = QdrantRoutingIndex.from_provider_config(configuration)
    try:
        report = await reindex_canonical_routing_cards(index, configuration)
        print(report)
    finally:
        await index.aclose()


if __name__ == "__main__":
    asyncio.run(main())
