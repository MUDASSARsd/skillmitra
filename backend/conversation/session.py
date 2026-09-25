"""Small orchestration layer joining extraction and counter-question logic."""
from dataclasses import dataclass
from typing import Optional
import re
from backend.models.beneficiary import BeneficiaryProfile
from backend.nlu.base import ProfileExtractor
from backend.conversation.completeness import CompletenessReport, ProfileCompletenessChecker
from backend.conversation.questions import CounterQuestionEngine, employment_clarifier


@dataclass
class ConversationTurn:
    profile: BeneficiaryProfile
    completeness: CompletenessReport
    next_question: Optional[str]


class ConversationManager:
    def __init__(self, extractor: ProfileExtractor):
        self.extractor = extractor
        self.checker = ProfileCompletenessChecker()
        self.questions = CounterQuestionEngine(self.checker)

    @staticmethod
    def _generic_preference_affirmation(text: str) -> bool:
        """True when the user agrees/wants something but did not choose one of the 3 options."""
        t = re.sub(r"[.!?,;:]+", " ", (text or "").lower()).strip()
        if not t or len(t.split()) > 7:
            return False
        option = re.search(
            r"\b(?:job|business|self[- ]?employment|naukri)\b|"
            r"नौकरी|जॉब|बिज(?:नेस|़नेस)|व्यापार|स्वरोज|खुद का काम|अपना काम|"
            r"ఉద్యోగం|జాబ్|బిజినెస్|స్వయం ఉపాధి|"
            r"வேலை|சுயதொழில்|வியாபாரம்|ಉದ್ಯೋಗ|ಸ್ವಯಂ ಉದ್ಯೋಗ|ವ್ಯವಹಾರ|"
            r"ജോലി|സ്വയംതൊഴിൽ|ബിസിനസ്|नोकरी|स्वयंरोजगार|व्यवसाय|"
            r"চাকরি|ব্যবসা|স্বনিয়োজিত|નોકરી|સ્વરોજગાર|વ્યવસાય|"
            r"ਨੌਕਰੀ|ਸਵੈ-ਰੋਜ਼ਗਾਰ|ਕਾਰੋਬਾਰ|ଚାକିରି|ସ୍ୱୟଂରୋଜଗାର|ବ୍ୟବସାୟ",
            t,
        )
        if option:
            return False
        return bool(re.search(
            r"\b(?:yes|yeah|yep|haan|han|ha|want|interested)\b|"
            r"हाँ|हां|हा|जी|चाहता|चाहती|चाहूँ|चाहूंगा|चाहूंगी|"
            r"అవును|కావాలి|చేయాలి|விரும்புகிறேன்|ஆம்|ಹೌದು|ಬೇಕು|അതെ|വേണം|"
            r"हो|हवे|হ্যাঁ|চাই|હા|જોઈએ|ਹਾਂ|ਚਾਹੁੰਦਾ|ଚਾਹੁੰਦੀ|ହଁ|ଚାହୁଁଛି",
            t,
        ))

    def process(self, text: str, current_profile: Optional[BeneficiaryProfile] = None,
                language_code: Optional[str] = None) -> ConversationTurn:
        expected_before = self.questions.next_missing_field(current_profile) if current_profile else None
        profile = self.extractor.extract(text, current_profile, language_code)
        # The UI-selected language is authoritative for this conversation turn.
        if language_code:
            profile.language = language_code
        completeness = self.checker.check(profile)
        question = self.questions.next_question(profile, language_code)
        if (expected_before == "employment_preference"
                and profile.employment_preference is None
                and self._generic_preference_affirmation(text)):
            question = employment_clarifier(language_code or profile.language)
        return ConversationTurn(profile, completeness, question)
