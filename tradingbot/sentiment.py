"""Lexicon Sentiment Analysis Engine.

Performs string sentiment evaluations based on a dictionary of positive
and negative financial/market keywords.
"""
from __future__ import annotations

import re


class LexiconSentimentModel:
    def __init__(self):
        # Weighted dictionary of market sentiment indicators
        self.lexicon = {
            # Positive indicators
            "upgrade": 1.0,
            "bullish": 1.0,
            "profit": 0.8,
            "profits": 0.8,
            "gain": 0.6,
            "gains": 0.6,
            "rise": 0.5,
            "grow": 0.6,
            "growth": 0.6,
            "buy": 0.5,
            "beat": 0.7,
            "success": 0.8,
            "successful": 0.8,
            "high": 0.3,
            "positive": 0.6,
            "partnership": 0.7,
            "surpass": 0.8,
            "exceed": 0.7,
            "exceeds": 0.7,
            "record": 0.5,
            "expansion": 0.6,
            "breakthrough": 0.9,
            "rally": 0.8,
            "optimism": 0.7,
            "acquire": 0.6,
            
            # Negative indicators
            "downgrade": -1.0,
            "bearish": -1.0,
            "loss": -0.8,
            "losses": -0.8,
            "crash": -1.0,
            "fall": -0.5,
            "decline": -0.6,
            "declines": -0.6,
            "scam": -0.9,
            "lawsuit": -0.8,
            "deficit": -0.7,
            "selloff": -0.8,
            "negative": -0.6,
            "warn": -0.5,
            "warning": -0.5,
            "drop": -0.5,
            "drops": -0.5,
            "plunge": -0.8,
            "shrink": -0.6,
            "investigation": -0.7,
            "fine": -0.6,
            "debt": -0.5,
            "fear": -0.7,
            "hack": -0.9,
            "risk": -0.4
        }

    def analyze_sentiment(self, text: str) -> float:
        """Analyze text and return a sentiment score between -1.0 and 1.0."""
        text = text.lower()
        # Clean text to alphanumeric/whitespace
        words = re.findall(r"\b[a-z]+\b", text)
        
        score = 0.0
        match_count = 0
        
        for w in words:
            if w in self.lexicon:
                score += self.lexicon[w]
                match_count += 1
                
        if match_count == 0:
            return 0.0  # Neutral
            
        # Normalize score
        normalized = score / match_count
        return max(-1.0, min(1.0, normalized))

    def get_sentiment_label(self, score: float) -> str:
        """Return a readable label for a given score."""
        if score > 0.15:
            return "Positive"
        elif score < -0.15:
            return "Negative"
        else:
            return "Neutral"
