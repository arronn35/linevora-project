"""Uygulama giriş noktası ve modül bağlantıları."""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .api.router import router as base_router
from .api.router_catalog import router as catalog_router
from .api.router_inquiries import router as inquiries_router
from .api.router_pipeline import router as pipeline_router
from .api.router_marketplace import router as marketplace_router
from .api.router_quotes import router as quotes_router
from .api.router_reports import router as reports_router
from .api.router_ui import router as ui_router
from .audit.store import AuditStore, InMemoryAuditStore
from .catalog.store import CatalogStore, InMemoryCatalogStore, seed_demo_catalog
from .config import get_settings
from .files.store import BlobStore, LocalBlobStore
from .inquiries.store import InMemoryInquiryStore, InquiryStore
from .jobs.runner import JobRunner
from .jobs.store import InMemoryJobStore, JobStore
from .auth.tokens import RevokedTokens
from .marketplace.store import (
    AgreementStore,
    InMemoryAgreementStore,
    InMemoryListingStore,
    InMemoryMessageStore,
    InMemoryNotificationStore,
    InMemoryOfferStore,
    ListingStore,
    MessageStore,
    NotificationStore,
    OfferStore,
)
from .matching.matcher import LexicalMatcher
from .matching.vector_matcher import HybridMatcher, VectorMatcher
from .matching.store import (
    InMemoryRequirementStore,
    InMemorySuggestionStore,
    RequirementStore,
    SuggestionStore,
)
from .model.client import FakeModelClient, HttpModelClient, MeteringClient, ModelClient
from .observability.metrics import MetricsRegistry
from .observability.middleware import RateLimiter, setup_observability
from .persistence import wrap_store
from .observability.snapshot import SnapshotManager
from .quotes.store import (
    InMemoryPriceStore,
    InMemoryQuoteLineStore,
    InMemoryQuoteStore,
    InMemoryTermsStore,
    PriceStore,
    QuoteLineStore,
    QuoteStore,
    TermsStore,
    seed_demo_prices,
    seed_demo_terms,
)
from .reports.store import (
    AlternativeStore,
    GapStore,
    InMemoryAlternativeStore,
    InMemoryGapStore,
)


def create_app(
    audit_store: AuditStore | None = None,
    inquiry_store: InquiryStore | None = None,
    blob_store: BlobStore | None = None,
    catalog_store: CatalogStore | None = None,
    requirement_store: RequirementStore | None = None,
    suggestion_store: SuggestionStore | None = None,
    gap_store: GapStore | None = None,
    alternative_store: AlternativeStore | None = None,
    price_store: PriceStore | None = None,
    terms_store: TermsStore | None = None,
    quote_store: QuoteStore | None = None,
    line_store: QuoteLineStore | None = None,
    job_store: JobStore | None = None,
    marketplace_listing_store: ListingStore | None = None,
    marketplace_offer_store: OfferStore | None = None,
    marketplace_agreement_store: AgreementStore | None = None,
    marketplace_message_store: MessageStore | None = None,
    marketplace_notification_store: NotificationStore | None = None,
    model_client: ModelClient | None = None,
    inline_jobs: bool = False,
    snapshot_path: str | None = None,
) -> FastAPI:
    settings = get_settings()
    if settings.env == "prod":
        if not settings.db_path and not settings.snapshot_path:
            raise RuntimeError(
                "üretimde kalıcılık zorunlu: LINEVORA_DB_PATH veya "
                "LINEVORA_SNAPSHOT_PATH tanımlanmalı"
            )
        plain = [u for u, (pw, _r, *_t) in settings.users.items() if not pw.startswith("pbkdf2_sha256$")]
        if plain:
            raise RuntimeError(f"üretimde düz metin parola kabul edilmez: {plain}")
    if settings.db_url:
        from .db.migrations import parse_db_url

        driver, target = parse_db_url(settings.db_url)
        if driver == "postgresql":
            try:
                import psycopg  # noqa: F401
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL için psycopg sürücüsü gerekli; "
                    "kurun veya sqlite LINEVORA_DB_URL kullanın"
                ) from exc
            raise RuntimeError(
                "PostgreSQL repository katmanı Faz 3 tetikleyicisinde; "
                "şema db/migrations.py içinde hazır (POSTGRES_DDL)"
            )
        db_path = target or None
    else:
        db_path = settings.db_path or None
    app = FastAPI(title="Linevora API", version=__version__)
    if catalog_store is None:
        catalog_store = wrap_store(InMemoryCatalogStore(), db_path, "catalog")
        if settings.seed_demo and not catalog_store.list():
            seed_demo_catalog(catalog_store)
    app.state.audit_store = wrap_store(
        audit_store if audit_store is not None else InMemoryAuditStore(),
        db_path if audit_store is None else None,
        "audit",
    )
    app.state.inquiry_store = wrap_store(
        inquiry_store if inquiry_store is not None else InMemoryInquiryStore(),
        db_path if inquiry_store is None else None,
        "inquiries",
    )
    app.state.blob_store = (
        blob_store if blob_store is not None else LocalBlobStore(settings.blob_dir)
    )
    app.state.catalog_store = catalog_store
    app.state.requirement_store = wrap_store(
        requirement_store if requirement_store is not None else InMemoryRequirementStore(),
        db_path if requirement_store is None else None,
        "requirements",
    )
    app.state.suggestion_store = wrap_store(
        suggestion_store if suggestion_store is not None else InMemorySuggestionStore(),
        db_path if suggestion_store is None else None,
        "suggestions",
    )
    app.state.gap_store = wrap_store(
        gap_store if gap_store is not None else InMemoryGapStore(),
        db_path if gap_store is None else None,
        "gaps",
    )
    app.state.alternative_store = wrap_store(
        alternative_store
        if alternative_store is not None
        else InMemoryAlternativeStore(),
        db_path if alternative_store is None else None,
        "alternatives",
    )
    app.state.price_store = wrap_store(
        price_store if price_store is not None else InMemoryPriceStore(),
        db_path if price_store is None else None,
        "prices",
    )
    app.state.terms_store = wrap_store(
        terms_store if terms_store is not None else InMemoryTermsStore(),
        db_path if terms_store is None else None,
        "terms",
    )
    _products = app.state.catalog_store.list()
    if settings.seed_demo and price_store is None and not (
        _products and app.state.price_store.list_for_product(_products[0].id)
    ):
        seed_demo_prices(app.state.price_store, _products)
    if settings.seed_demo and terms_store is None and not app.state.terms_store.list():
        seed_demo_terms(app.state.terms_store)
    app.state.quote_store = wrap_store(
        quote_store if quote_store is not None else InMemoryQuoteStore(),
        db_path if quote_store is None else None,
        "quotes",
    )
    app.state.line_store = wrap_store(
        line_store if line_store is not None else InMemoryQuoteLineStore(),
        db_path if line_store is None else None,
        "lines",
    )
    app.state.job_store = wrap_store(
        job_store if job_store is not None else InMemoryJobStore(),
        db_path if job_store is None else None,
        "jobs",
    )
    app.state.marketplace_listing_store = wrap_store(
        marketplace_listing_store
        if marketplace_listing_store is not None
        else InMemoryListingStore(),
        db_path if marketplace_listing_store is None else None,
        "marketplace_listings",
    )
    app.state.marketplace_offer_store = wrap_store(
        marketplace_offer_store
        if marketplace_offer_store is not None
        else InMemoryOfferStore(),
        db_path if marketplace_offer_store is None else None,
        "marketplace_offers",
    )
    app.state.marketplace_agreement_store = wrap_store(
        marketplace_agreement_store
        if marketplace_agreement_store is not None
        else InMemoryAgreementStore(),
        db_path if marketplace_agreement_store is None else None,
        "marketplace_agreements",
    )
    app.state.marketplace_message_store = wrap_store(
        marketplace_message_store
        if marketplace_message_store is not None
        else InMemoryMessageStore(),
        db_path if marketplace_message_store is None else None,
        "marketplace_messages",
    )
    app.state.marketplace_notification_store = wrap_store(
        marketplace_notification_store
        if marketplace_notification_store is not None
        else InMemoryNotificationStore(),
        db_path if marketplace_notification_store is None else None,
        "marketplace_notifications",
    )
    app.state.revoked_tokens = RevokedTokens()
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    if model_client is not None:
        app.state.model_client = model_client
    elif settings.model_url:
        app.state.model_client = HttpModelClient(
            settings.model_url,
            api_key=settings.model_api_key,
            model=settings.model_name,
            timeout_seconds=settings.model_timeout_seconds,
        )
    else:
        app.state.model_client = FakeModelClient({})
    app.state.metrics = MetricsRegistry()
    resolved_snapshot = (
        snapshot_path if snapshot_path is not None else (get_settings().snapshot_path or None)
    )
    if resolved_snapshot is not None:
        candidates = {
            "audit": app.state.audit_store,
            "inquiries": app.state.inquiry_store,
            "catalog": app.state.catalog_store,
            "requirements": app.state.requirement_store,
            "suggestions": app.state.suggestion_store,
            "gaps": app.state.gap_store,
            "alternatives": app.state.alternative_store,
            "prices": app.state.price_store,
            "terms": app.state.terms_store,
            "quotes": app.state.quote_store,
            "lines": app.state.line_store,
            "jobs": app.state.job_store,
            "marketplace_listings": app.state.marketplace_listing_store,
            "marketplace_offers": app.state.marketplace_offer_store,
            "marketplace_agreements": app.state.marketplace_agreement_store,
            "marketplace_messages": app.state.marketplace_message_store,
            "marketplace_notifications": app.state.marketplace_notification_store,
        }
        providers = {
            name: (store.to_snapshot, store.load_snapshot)
            for name, store in candidates.items()
            if hasattr(store, "to_snapshot") and hasattr(store, "load_snapshot")
        }
        manager = SnapshotManager(resolved_snapshot, providers)
        manager.load()
    else:
        manager = None
    app.state.snapshot = manager

    if settings.matcher not in ("lexical", "vector", "hybrid", "embedding"):
        raise ValueError(
            f"geçersiz LINEVORA_MATCHER: {settings.matcher!r} "
            "(lexical|vector|hybrid|embedding)"
        )
    if settings.matcher == "embedding":
        from .matching.embedder import HashingEmbedder, HttpEmbedder
        from .matching.vector_matcher import EmbeddingMatcher

        embedder = (
            HttpEmbedder(
                settings.embedding_url,
                api_key=settings.embedding_api_key,
                model=settings.embedding_model,
            )
            if settings.embedding_url
            else HashingEmbedder()
        )
        matcher = EmbeddingMatcher(embedder)
    else:
        matcher = {
            "lexical": LexicalMatcher(),
            "vector": VectorMatcher(),
            "hybrid": HybridMatcher(),
        }[settings.matcher]

    from .pipeline import ProcessVersionService

    handle_process_version = ProcessVersionService(
        inquiry_store=app.state.inquiry_store,
        requirement_store=app.state.requirement_store,
        suggestion_store=app.state.suggestion_store,
        alternative_store=app.state.alternative_store,
        gap_store=app.state.gap_store,
        catalog_store=app.state.catalog_store,
        matcher=matcher,
        get_model_client=lambda: app.state.model_client,
        set_model_client=lambda c: setattr(app.state, "model_client", c),
    )

    app.state.job_runner = JobRunner(
        store=app.state.job_store,
        audit=app.state.audit_store,
        handlers={"process_version": handle_process_version},
        inline=inline_jobs,
    )
    setup_observability(app)
    app.include_router(base_router, prefix="/v1")
    app.include_router(catalog_router, prefix="/v1")
    app.include_router(inquiries_router, prefix="/v1")
    app.include_router(pipeline_router, prefix="/v1")
    app.include_router(reports_router, prefix="/v1")
    app.include_router(quotes_router, prefix="/v1")
    app.include_router(marketplace_router, prefix="/v1")
    app.include_router(ui_router)
    return app


app = create_app()
