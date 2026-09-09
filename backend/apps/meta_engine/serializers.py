"""
Dynamic Serializers for Metadata-Driven Entity Gateway.

Constructs live DRF ModelSerializer classes in memory for dynamic models,
automatically mapping fields, handling relational lookups, and injecting audit trails.
"""

from typing import Any, Dict, Type

from rest_framework import serializers

from apps.meta_engine.models import MetaModel, SystemModule


class SystemModuleSerializer(serializers.ModelSerializer):
    """Serializer for SystemModule registry records."""
    class Meta:
        model = SystemModule
        fields = (
            "id",
            "app_id",
            "name",
            "version",
            "category",
            "icon",
            "summary",
            "description",
            "author",
            "website",
            "license",
            "status",
            "dependencies",
            "installed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "installed_at", "created_at", "updated_at")


class DynamicEntitySerializerFactory:
    """
    Factory generating dynamic DRF serializers for in-memory dynamic models.
    """

    _serializer_cache: Dict[str, Type[serializers.ModelSerializer]] = {}

    @classmethod
    def get_serializer_class(
        cls,
        meta_model: MetaModel,
        model_cls: Type[Any],
        force_reload: bool = False,
    ) -> Type[serializers.ModelSerializer]:
        """
        Dynamically construct and return a ModelSerializer for model_cls.
        """
        cache_key = f"{meta_model.name}_{model_cls.__name__}"
        if not force_reload and cache_key in cls._serializer_cache:
            return cls._serializer_cache[cache_key]

        class DynamicMeta:
            model = model_cls
            fields = "__all__"
            read_only_fields = ("id", "created_at", "updated_at", "created_by", "updated_by")

        serializer_attrs = {
            "Meta": DynamicMeta,
        }

        # Dynamically create serializer class
        serializer_name = f"{model_cls.__name__}Serializer"
        serializer_cls = type(
            serializer_name,
            (serializers.ModelSerializer,),
            serializer_attrs,
        )

        cls._serializer_cache[cache_key] = serializer_cls
        return serializer_cls
