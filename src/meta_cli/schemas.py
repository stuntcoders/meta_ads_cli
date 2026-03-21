from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from meta_cli.exceptions import ConfigError


class AdSetCreateConfig(BaseModel):
    campaign_id: str
    name: str
    daily_budget: Optional[int] = None
    lifetime_budget: Optional[int] = None
    billing_event: Optional[str] = None
    optimization_goal: Optional[str] = None
    bid_strategy: Optional[str] = None
    bid_amount: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    targeting: Dict[str, Any] = Field(default_factory=dict)
    status: str = "PAUSED"
    promoted_object: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_budget(self) -> "AdSetCreateConfig":
        if self.daily_budget is None and self.lifetime_budget is None:
            raise ValueError("One of daily_budget or lifetime_budget is required")
        return self

    def to_payload(self) -> Dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        return payload


class AdCreateConfig(BaseModel):
    adset_id: str
    name: str
    page_id: Optional[str] = None
    instagram_actor_id: Optional[str] = None
    destination_url: Optional[str] = None
    headlines: List[str] = Field(default_factory=list)
    bodies: List[str] = Field(default_factory=list)
    descriptions: List[str] = Field(default_factory=list)
    image_hashes: List[str] = Field(default_factory=list)
    video_id: Optional[str] = None
    call_to_action_type: Optional[str] = "LEARN_MORE"
    status: str = "PAUSED"
    existing_creative_id: Optional[str] = None

    @field_validator("headlines", "bodies", "descriptions", "image_hashes", mode="before")
    @classmethod
    def normalize_list_values(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        raise ValueError("Expected a string or list")

    @model_validator(mode="after")
    def validate_payload_requirements(self) -> "AdCreateConfig":
        if self.existing_creative_id:
            return self
        if not self.page_id:
            raise ValueError("page_id is required unless existing_creative_id is provided")
        if not self.bodies:
            raise ValueError("At least one body text is required")
        if not self.destination_url:
            raise ValueError("destination_url is required")
        if not self.image_hashes and not self.video_id:
            raise ValueError("Provide image_hashes or video_id")
        return self

    def uses_asset_feed_spec(self) -> bool:
        return (
            len(self.headlines) > 1
            or len(self.bodies) > 1
            or len(self.descriptions) > 1
            or len(self.image_hashes) > 1
        )

    def build_creative_payload(self) -> Dict[str, Any]:
        if self.existing_creative_id:
            raise ValueError("Creative payload not required when existing_creative_id is set")

        base_story_spec: Dict[str, Any] = {"page_id": self.page_id}
        if self.instagram_actor_id:
            base_story_spec["instagram_actor_id"] = self.instagram_actor_id

        if self.uses_asset_feed_spec():
            asset_feed_spec: Dict[str, Any] = {
                "bodies": [{"text": text} for text in self.bodies],
                "titles": [{"text": text} for text in self.headlines] if self.headlines else [],
                "link_urls": [{"website_url": self.destination_url}],
            }
            if self.descriptions:
                asset_feed_spec["descriptions"] = [{"text": text} for text in self.descriptions]
            if self.image_hashes:
                asset_feed_spec["images"] = [{"hash": image_hash} for image_hash in self.image_hashes]
                asset_feed_spec["ad_formats"] = ["SINGLE_IMAGE"]
            if self.video_id:
                asset_feed_spec["videos"] = [{"video_id": self.video_id}]
                asset_feed_spec["ad_formats"] = ["SINGLE_VIDEO"]
            if self.call_to_action_type:
                asset_feed_spec["call_to_action_types"] = [self.call_to_action_type]

            payload = {
                "name": f"{self.name} - creative",
                "object_story_spec": base_story_spec,
                "asset_feed_spec": asset_feed_spec,
            }
            return payload

        body_text = self.bodies[0]
        headline = self.headlines[0] if self.headlines else None
        description = self.descriptions[0] if self.descriptions else None

        if self.video_id:
            video_data: Dict[str, Any] = {
                "video_id": self.video_id,
                "message": body_text,
            }
            if headline:
                video_data["title"] = headline
            if description:
                video_data["description"] = description
            if self.call_to_action_type:
                video_data["call_to_action"] = {
                    "type": self.call_to_action_type,
                    "value": {"link": self.destination_url},
                }
            base_story_spec["video_data"] = video_data
        else:
            link_data: Dict[str, Any] = {
                "message": body_text,
                "link": self.destination_url,
                "image_hash": self.image_hashes[0],
            }
            if headline:
                link_data["name"] = headline
            if description:
                link_data["description"] = description
            if self.call_to_action_type:
                link_data["call_to_action"] = {
                    "type": self.call_to_action_type,
                    "value": {"link": self.destination_url},
                }
            base_story_spec["link_data"] = link_data

        return {"name": f"{self.name} - creative", "object_story_spec": base_story_spec}

    def build_ad_payload(self, creative_id: str) -> Dict[str, Any]:
        return {
            "name": self.name,
            "adset_id": self.adset_id,
            "creative": {"creative_id": creative_id},
            "status": self.status,
        }


def load_yaml_model(path: str, model_class: Any) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(file_path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a mapping: {path}")
    try:
        return model_class.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid config in {path}: {exc}") from exc
