"""Phrase bank voice: varied wording without any AI. Seeded per run, never repeats the previous pick."""
import random
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Voice:
    def __init__(self, bank, bot, user, seed, last=None, address="sir"):
        self.bank, self.bot, self.user, self.address = bank, bot, user, address
        self.rng = random.Random(seed)
        self.last = dict(last or {})
        self.used = {}

    @classmethod
    def load(cls, bot, user, seed, last=None, path=None, address="sir"):
        with open(path or ROOT / "phrases.toml", "rb") as f:
            return cls(tomllib.load(f), bot, user, seed, last, address)

    def maybe(self, key, p):
        """Say something from `key` with probability p, else nothing. Always consumes the same randomness."""
        roll = self.rng.random()
        if key not in self.bank or roll >= p:
            return ""
        return self.say(key)

    def say(self, key, **kw):
        options = self.bank[key]
        idx = [i for i in range(len(options)) if i != self.last.get(key)] or [0]
        i = self.rng.choice(idx)
        self.used[key] = i
        text = options[i].format(name=self.user, bot=self.bot, sir=self.address, **kw)
        return text[:1].upper() + text[1:]
