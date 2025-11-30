from dataclasses import dataclass
import arrow


@dataclass(frozen=True)
class TrustStats:
    user_id: str
    trust_level: int
    trust_value: int

    @classmethod
    def parse(cls, user_id: str, data: dict) -> "TrustStats":
        return cls(
            user_id=user_id,
            trust_level=data["trust_level"],
            trust_value=data["trust_value"],
        )
    

@dataclass(frozen=True)
class LanguageStats:
    user_id: str
    name: str
    total_seconds: int
    percent: float

    @classmethod
    def parse(cls, user_id: str, data: dict) -> "LanguageStats":
        return cls(
            user_id=user_id,
            name=data["name"],
            total_seconds=data["total_seconds"],
            percent=data["percent"],
        )
    
    @property
    def language(self) -> str:
        return self.name

@dataclass(frozen=True)
class UserStats:
    username: str
    user_id: str
    is_coding_activity_visible: bool
    is_other_usage_visible: bool
    status: str
    start: arrow.Arrow
    end: arrow.Arrow
    total_seconds: int
    daily_average: int
    languages: list[LanguageStats]
    trust: TrustStats

    @classmethod
    def parse(cls, data: dict) -> "UserStats":
        return cls(
            username=data["username"],
            user_id=data["user_id"],
            is_coding_activity_visible=data["is_coding_activity_visible"],
            is_other_usage_visible=data["is_other_usage_visible"],
            status=data["status"],
            start=arrow.get(data["start"]),
            end=arrow.get(data["end"]),
            total_seconds=data["total_seconds"],
            daily_average=data["daily_average"],
            languages=[
                LanguageStats.parse(data["user_id"], lang)
                for lang in data.get("languages", [])
            ],
            trust=TrustStats.parse(data["user_id"], data.get("trust", {})),
        ) 


