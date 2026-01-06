"""Application configuration and environment settings for EPIP."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from epip.core.entity_extractor import EntityExtractionConfig
    from epip.core.kg_quality import QualityThresholds
    from epip.core.relation_extractor import RelationExtractionConfig


class Settings(BaseSettings):
    """Runtime configuration pulled from environment variables."""

    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    redis_url: str = "redis://localhost:6379/0"
    llm_backend: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LightRAGConfig(BaseSettings):
    """Configuration for Light-RAG integrations."""

    working_dir: str = "./data/lightrag"
    graph_storage: Literal["neo4j", "networkx"] = "neo4j"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # LLM 配置
    llm_backend: Literal["ollama", "openai"] = Field(
        default="ollama",
        validation_alias=AliasChoices("LLM_BINDING", "llm_backend"),
    )
    llm_model: str = Field(
        default="qwen-plus",
        validation_alias=AliasChoices("LLM_MODEL", "llm_model"),
    )
    llm_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "llm_base_url"),
    )
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "llm_api_key"),
    )
    llm_timeout: int = Field(
        default=120,
        validation_alias=AliasChoices("LLM_TIMEOUT", "llm_timeout"),
    )

    # Ollama 本地配置 (备用)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # 兼容旧配置
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Embedding 配置
    embedding_model: str = Field(
        default="text-embedding-v4",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "embedding_model"),
    )
    embedding_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("EMBEDDING_BASE_URL", "embedding_base_url"),
    )
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EMBEDDING_API_KEY", "embedding_api_key"),
    )
    embedding_dim: int = Field(
        default=1024,
        validation_alias=AliasChoices("EMBEDDING_DIM", "embedding_dim"),
    )

    chunk_size: int = 1200
    chunk_overlap: int = 100
    max_tokens: int = 32768

    # 并发控制
    max_concurrent_llm: int = 2  # LLM 并发数
    max_concurrent_embed: int = 4  # 嵌入并发数

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class CypherExecutorSettings(BaseSettings):
    """Settings controlling Cypher executor behavior."""

    timeout: float = 5.0
    max_retries: int = 1

    model_config = SettingsConfigDict(
        env_prefix="CYPHER_EXECUTOR_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ReActSettings(BaseSettings):
    """Runtime knobs for the ReAct reasoning agent."""

    max_iterations: int = 5
    timeout_per_step: float = 10.0

    model_config = SettingsConfigDict(
        env_prefix="REACT_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class EntityExtractionSettings(BaseSettings):
    """Environment-aware settings for entity extraction."""

    confidence_threshold: float = 0.6
    entity_types: list[str] = [
        "POLICY",
        "ORGANIZATION",
        "PERSON",
        "LOCATION",
        "DATE",
        "METRIC",
        "DISEASE",
        "BUDGET",
    ]
    max_entities_per_chunk: int = 50
    enable_disambiguation: bool = True
    similarity_threshold: float = 0.85
    report_sample_size: int = 20

    model_config = SettingsConfigDict(
        env_prefix="ENTITY_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def as_config(self) -> EntityExtractionConfig:
        from epip.core.entity_extractor import EntityExtractionConfig

        return EntityExtractionConfig(
            confidence_threshold=self.confidence_threshold,
            entity_types=list(self.entity_types),
            max_entities_per_chunk=self.max_entities_per_chunk,
            enable_disambiguation=self.enable_disambiguation,
            similarity_threshold=self.similarity_threshold,
            report_sample_size=self.report_sample_size,
        )


class RelationExtractionSettings(BaseSettings):
    """Environment-aware settings for relation analysis."""

    confidence_threshold: float = 0.5
    relation_types: list[str] = [
        "ASSOCIATED_WITH",
        "SUPPORTED_BY",
        "FUNDED_BY",
        "COORDINATES_WITH",
        "LOCATED_IN",
    ]
    default_relation_type: str = "ASSOCIATED_WITH"
    report_sample_size: int = 25

    model_config = SettingsConfigDict(
        env_prefix="RELATION_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def as_config(self) -> RelationExtractionConfig:
        from epip.core.relation_extractor import RelationExtractionConfig

        return RelationExtractionConfig(
            confidence_threshold=self.confidence_threshold,
            relation_types=list(self.relation_types),
            default_relation_type=self.default_relation_type,
            report_sample_size=self.report_sample_size,
        )


class QualitySettings(BaseSettings):
    """Settings for KG quality evaluation thresholds and defaults."""

    ground_truth_path: str = "data/ground_truth/expected_kg.yaml"
    markdown_report: str = "data/reports/kg_quality.md"
    json_report: str = "data/reports/kg_quality.json"

    entity_precision: float = 0.8
    entity_recall: float = 0.75
    relation_coverage: float = 0.7
    graph_density: float = 0.01
    min_avg_degree: float = 1.0
    max_isolated_ratio: float = 0.1

    model_config = SettingsConfigDict(
        env_prefix="QUALITY_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def as_thresholds(self) -> QualityThresholds:
        from epip.core.kg_quality import QualityThresholds

        return QualityThresholds(
            entity_precision=self.entity_precision,
            entity_recall=self.entity_recall,
            relation_coverage=self.relation_coverage,
            graph_density=self.graph_density,
            min_avg_degree=self.min_avg_degree,
            max_isolated_ratio=self.max_isolated_ratio,
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance for dependency injection."""
    return Settings()


settings = get_settings()


@lru_cache
def get_entity_extraction_config() -> EntityExtractionConfig:
    """Expose an EntityExtractionConfig built from environment variables."""
    return EntityExtractionSettings().as_config()


@lru_cache
def get_relation_extraction_config() -> RelationExtractionConfig:
    """Expose a RelationExtractionConfig built from environment variables."""
    return RelationExtractionSettings().as_config()


@lru_cache
def get_quality_settings() -> QualitySettings:
    """Expose cached KG quality settings."""
    return QualitySettings()


@lru_cache
def get_quality_thresholds() -> QualityThresholds:
    """Return quality thresholds derived from environment variables."""
    return QualitySettings().as_thresholds()


@lru_cache
def get_cypher_executor_settings() -> CypherExecutorSettings:
    """Expose cached Cypher executor settings."""
    return CypherExecutorSettings()
