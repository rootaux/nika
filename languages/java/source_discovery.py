from .source_definitions import JAVA_SOURCE_DEFINITIONS


def select_source_definitions(source_types: list[str]) -> dict[str, list[str]]:
    unknown_source_types = [
        source_type
        for source_type in source_types
        if source_type not in JAVA_SOURCE_DEFINITIONS
    ]
    if unknown_source_types:
        raise ValueError(f"Unknown source types: {', '.join(unknown_source_types)}")

    return {
        source_type: JAVA_SOURCE_DEFINITIONS[source_type]
        for source_type in source_types
    }
