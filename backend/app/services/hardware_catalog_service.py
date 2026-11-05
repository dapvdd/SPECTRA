"""Server-side hardware catalog query, pagination, and facets (Phase 1.3).

All parameters are additive: with no arguments the function returns the full
catalog in the existing order, preserving the pre-1.3 behavior exactly. When
``limit``/``offset`` are present the result is a page; the total count is
returned on the ``HardwareCatalogPage`` so callers can page without guessing.
Facet counts are computed from the same filters and are therefore always
accurate for the active filter set.
"""

from sqlalchemy import func, select

from backend.app.database import SessionLocal
from backend.app.models import Hardware


def query_hardware(
    *,
    hardware_type: str | None = None,
    q: str | None = None,
    manufacturer: str | None = None,
    segment: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[Hardware], int]:
    """Return ``(page_items, total_count)`` for the active filter set.

    The total count reflects every filter (q/type/manufacturer/segment) with
    pagination applied to the items only, so ``total`` always refers to the
    full filtered result set, not the page.
    """
    statement = select(Hardware)
    count_statement = select(func.count()).select_from(Hardware)

    if hardware_type is not None:
        statement = statement.where(Hardware.type == hardware_type)
        count_statement = count_statement.where(Hardware.type == hardware_type)

    if q:
        # Case-insensitive substring match across the name. An empty search is
        # treated as "no filter" rather than an exact-empty match.
        pattern = f"%{q}%"
        statement = statement.where(Hardware.name.ilike(pattern))
        count_statement = count_statement.where(Hardware.name.ilike(pattern))

    if manufacturer is not None:
        statement = statement.where(Hardware.manufacturer == manufacturer)
        count_statement = count_statement.where(
            Hardware.manufacturer == manufacturer
        )

    if segment is not None:
        statement = statement.where(Hardware.segment == segment)
        count_statement = count_statement.where(Hardware.segment == segment)

    with SessionLocal() as session:
        total = session.scalar(count_statement)

        if limit is not None:
            statement = statement.limit(limit).offset(offset)
        elif offset > 0:
            statement = statement.offset(offset)

        page = list(session.scalars(statement).all())

    return page, total


def get_hardware_facets(
    *,
    hardware_type: str | None = None,
    q: str | None = None,
    manufacturer: str | None = None,
    segment: str | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Accurate facet counts for the active filter set.

    Each facet list (types, manufacturers, segments) is counted with the same
    WHERE clauses the query applies, so a facet count always reflects the rows
    currently visible under the other active filters. ``None`` facet values are
    excluded: a missing value is unknown and is not reported as a facet.
    """
    base_filters = []
    if hardware_type is not None:
        base_filters.append(Hardware.type == hardware_type)
    if q:
        pattern = f"%{q}%"
        base_filters.append(Hardware.name.ilike(pattern))
    if manufacturer is not None:
        base_filters.append(Hardware.manufacturer == manufacturer)
    if segment is not None:
        base_filters.append(Hardware.segment == segment)

    facets: dict[str, list[dict[str, object]]] = {}

    for label, column in (
        ("types", Hardware.type),
        ("manufacturers", Hardware.manufacturer),
        ("segments", Hardware.segment),
    ):
        statement = (
            select(column, func.count())
            .where(*base_filters)
            .where(column.is_not(None))
            .group_by(column)
            .order_by(func.count().desc(), column.asc())
        )
        with SessionLocal() as session:
            rows = session.execute(statement).all()

        facets[label] = [
            {"value": value, "count": count}
            for value, count in rows
        ]

    return facets
