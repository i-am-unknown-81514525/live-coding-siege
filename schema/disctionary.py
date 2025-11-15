from dataclasses import dataclass
from typing import TypedDict, Self
from abc import ABC, abstractmethod


class Readable(ABC):
    @property
    @abstractmethod
    def readable(self) -> str: ...

class RawDictError(TypedDict):
    title: str
    message: str
    resolution: str

@dataclass(frozen=True)
class License(Readable):
    name: str
    url: str

    @property
    def readable(self) -> str:
        return f"<{self.url}|{self.name}>"
    
    @classmethod
    def parse(cls, raw: dict) -> Self:
        return cls(**raw)

@dataclass(frozen=True)
class DictError(Readable):
    title: str
    message: str
    resolution: str

    @property
    def readable(self) -> str:
        return f"*{self.title}*\n{self.message}\n{self.resolution}"
    
    @classmethod
    def parse(cls, raw: RawDictError) -> Self:
        return cls(**raw)

@dataclass(frozen=True)
class WordDef(Readable):
    definition: str
    synonyms: list[str]
    antonyms: list[str]

    @classmethod
    def parse(cls, raw: dict) -> Self:
        return cls(**raw)

    

@dataclass(frozen=True)
class WordDefPart(Readable):
    partOfSpeech: str
    synonyms: list[str]
    antonyms: list[str]
    definitions: list[WordDef]

    @classmethod
    def parse(cls, raw: dict) -> Self:
        return cls(
            partOfSpeech=raw["partOfSpeech"],
            synonyms=raw["synonyms"],
            antonyms=raw["antonyms"],
            definitions=[WordDef.parse(d) for d in raw["definitions"]],
        )

@dataclass(frozen=True)
class PhoneticsResult(Readable):
    text: str
    audio: str
    sourceUrl: str
    license: License

    @classmethod
    def parse(cls, raw: dict) -> Self:
        return cls(
            text=raw["text"],
            audio=raw["audio"],
            sourceUrl=raw["sourceUrl"],
            license=License.parse(raw["license"]),
        )


@dataclass(frozen=True)
class DictResult(Readable):
    word: str
    phonetic: str
    phonetics: list[PhoneticsResult]
    license: License
    sourceUrls: list[str]
    meanings: list[WordDefPart]

    @classmethod
    def parse(cls, raw: dict) -> Self:
        return cls(
            word=raw["word"],
            phonetic=raw["phonetic"],
            phonetics=[PhoneticsResult.parse(p) for p in raw["phonetics"]],
            license=License.parse(raw["license"]),
            sourceUrls=raw["sourceUrls"],
            meanings=[WordDefPart.parse(p) for p in raw["meanings"]],
        )