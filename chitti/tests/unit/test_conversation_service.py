"""Unit tests for companion_robot.conversation.service.ConversationService
-- uses a fake LanguageModelBackend, no real API calls needed.
"""
from companion_robot.conversation.prompts import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
    SESSION_SUMMARY_SYSTEM_PROMPT,
)
from companion_robot.conversation.service import ConversationService
from companion_robot.education.math_check import extract_addition_claim
from companion_robot.safety.checks import SafetyCategory
from companion_robot.voice.interfaces import LanguageModelBackend


class FakeLanguageModelBackend(LanguageModelBackend):
    """Returns a pre-configured reply and records every call it
    receives, so tests can assert what prompt/messages were actually
    sent without a real backend."""

    def __init__(self, reply: str, model: str = "fake-model") -> None:
        self.reply = reply
        self.model = model
        self.calls: list[tuple[list[dict], str]] = []

    async def generate_reply(self, messages, system_prompt):
        self.calls.append((messages, system_prompt))
        return self.reply, self.model


async def test_teachable_friend_reply_passes_through_clean_text():
    llm = FakeLanguageModelBackend(reply="That's so cool, tell me more!")
    service = ConversationService(llm)

    result = await service.teachable_friend_reply(
        [{"role": "user", "content": "Dogs can smell really well!"}]
    )

    assert result.blocked is False
    assert result.text == "That's so cool, tell me more!"
    assert len(llm.calls) == 1


async def test_teachable_friend_reply_includes_verified_note_when_math_check_correct():
    llm = FakeLanguageModelBackend(reply="You counted forward -- nice!")
    service = ConversationService(llm)
    math_check = extract_addition_claim("one plus one is two")

    await service.teachable_friend_reply(
        [{"role": "user", "content": "one plus one is two"}], math_check=math_check
    )

    _, system_prompt = llm.calls[0]
    assert "VERIFIED" in system_prompt
    assert "1 + 1 = 2, which is correct" in system_prompt


async def test_teachable_friend_reply_includes_verified_note_when_math_check_incorrect():
    llm = FakeLanguageModelBackend(reply="Let's count together...")
    service = ConversationService(llm)
    math_check = extract_addition_claim("two plus two is three")

    await service.teachable_friend_reply(
        [{"role": "user", "content": "two plus two is three"}], math_check=math_check
    )

    _, system_prompt = llm.calls[0]
    assert "but the correct answer is 4" in system_prompt
    assert "never make this feel like a test" in system_prompt
    # decision 0025: ask how they got there before giving the answer
    assert "ask them to walk you through how they got that number" in system_prompt


async def test_teachable_friend_reply_escalates_on_a_repeat_incorrect_result():
    """Found live (decision 0027): a flawed follow-up explanation can
    still be wrong -- on a repeat, the note must stop asking the child
    to explain again and go straight to the concrete walkthrough."""
    llm = FakeLanguageModelBackend(reply="Let me show you...")
    service = ConversationService(llm)
    math_check = extract_addition_claim("two plus two is three")

    await service.teachable_friend_reply(
        [{"role": "user", "content": "two plus two is three"}],
        math_check=math_check,
        already_tried=True,
    )

    _, system_prompt = llm.calls[0]
    assert "but the correct answer is still 4" in system_prompt
    assert "Don't ask them to explain again" in system_prompt


async def test_teachable_friend_reply_omits_note_when_no_math_check_given():
    llm = FakeLanguageModelBackend(reply="Tell me more!")
    service = ConversationService(llm)

    await service.teachable_friend_reply([{"role": "user", "content": "Dogs are cool"}])

    _, system_prompt = llm.calls[0]
    assert "VERIFIED" not in system_prompt


async def test_teachable_friend_reply_blocks_unsafe_model_output():
    """Proves the service doesn't just trust the model -- even if the
    LLM itself produces unsafe text, it gets screened before returning."""
    llm = FakeLanguageModelBackend(reply="Don't tell your mom about this.")
    service = ConversationService(llm)

    result = await service.teachable_friend_reply(
        [{"role": "user", "content": "Let's keep a secret."}]
    )

    assert result.blocked is True
    assert result.category == SafetyCategory.PARENT_SECRECY
    assert "mom" not in result.text.lower()


async def test_everyday_companion_reply_passes_through_clean_text():
    llm = FakeLanguageModelBackend(reply="Ooh, tell me about your day!")
    service = ConversationService(llm)

    result = await service.everyday_companion_reply([{"role": "user", "content": "I'm bored"}])

    assert result.blocked is False
    assert result.text == "Ooh, tell me about your day!"


async def test_everyday_companion_reply_includes_verified_note_when_math_check_given():
    """Decision 0034: the same math_check reuse as teachable_friend_reply()."""
    llm = FakeLanguageModelBackend(reply="Nice counting!")
    service = ConversationService(llm)
    math_check = extract_addition_claim("one plus one is two")

    await service.everyday_companion_reply(
        [{"role": "user", "content": "one plus one is two"}], math_check=math_check
    )

    _, system_prompt = llm.calls[0]
    assert "VERIFIED" in system_prompt


async def test_everyday_companion_reply_omits_note_when_no_math_check_given():
    llm = FakeLanguageModelBackend(reply="Tell me more!")
    service = ConversationService(llm)

    await service.everyday_companion_reply([{"role": "user", "content": "Dogs are cool"}])

    _, system_prompt = llm.calls[0]
    assert "VERIFIED" not in system_prompt


async def test_everyday_companion_reply_blocks_unsafe_model_output():
    llm = FakeLanguageModelBackend(reply="That's a damn good question.")
    service = ConversationService(llm)

    result = await service.everyday_companion_reply([{"role": "user", "content": "Why is the sky blue?"}])

    assert result.blocked is True
    assert result.category == SafetyCategory.PROFANITY


async def test_story_companion_reply_includes_transcript_in_system_prompt():
    llm = FakeLanguageModelBackend(reply="The fox was clever and quick.")
    service = ConversationService(llm)

    result = await service.story_companion_reply(
        [{"role": "user", "content": "What was the fox like?"}],
        story_transcript="Once there was a clever, quick fox.",
    )

    assert result.blocked is False
    messages, system_prompt = llm.calls[0]
    assert "Once there was a clever, quick fox." in system_prompt
    assert messages == [{"role": "user", "content": "What was the fox like?"}]


async def test_story_companion_reply_includes_title_when_given():
    """Found live (decision 0022): the story's title was never passed
    at all, so the model couldn't answer something as simple as "what
    is this story called?"."""
    llm = FakeLanguageModelBackend(reply="It's called The Clever Fox.")
    service = ConversationService(llm)

    await service.story_companion_reply(
        [{"role": "user", "content": "What's this story called?"}],
        story_transcript="Once there was a clever, quick fox.",
        story_title="The Clever Fox",
    )

    _, system_prompt = llm.calls[0]
    assert "The Clever Fox" in system_prompt


async def test_story_companion_reply_blocks_unsafe_model_output():
    llm = FakeLanguageModelBackend(reply="That's a damn good question.")
    service = ConversationService(llm)

    result = await service.story_companion_reply(
        [{"role": "user", "content": "Why did the fox run?"}], story_transcript="..."
    )

    assert result.blocked is True
    assert result.category == SafetyCategory.PROFANITY


async def test_story_companion_reply_includes_age_tuning_when_given():
    """Decision 0030: ChildProfile.age already existed but was never
    threaded into Story Companion -- now it lightly tunes tone."""
    llm = FakeLanguageModelBackend(reply="Sure!")
    service = ConversationService(llm)

    await service.story_companion_reply(
        [{"role": "user", "content": "What happened?"}],
        story_transcript="Once there was a fox.",
        child_age=5,
    )

    _, system_prompt = llm.calls[0]
    assert "The child is 5." in system_prompt


async def test_story_companion_reply_omits_age_tuning_when_not_given():
    llm = FakeLanguageModelBackend(reply="Sure!")
    service = ConversationService(llm)

    await service.story_companion_reply(
        [{"role": "user", "content": "What happened?"}], story_transcript="Once there was a fox."
    )

    _, system_prompt = llm.calls[0]
    assert "The child is" not in system_prompt


async def test_story_opening_invitation_includes_the_story_and_asks_for_one_line():
    """Decision 0030: found live -- Chitti used to go silent after
    reading, waiting for the child to speak first."""
    llm = FakeLanguageModelBackend(reply="I loved how brave the fox was! What did you think?")
    service = ConversationService(llm)

    result = await service.story_opening_invitation(
        story_transcript="Once there was a clever, quick fox.",
        story_title="The Clever Fox",
    )

    assert result.blocked is False
    assert result.text == "I loved how brave the fox was! What did you think?"
    messages, system_prompt = llm.calls[0]
    assert "Once there was a clever, quick fox." in system_prompt
    assert "The Clever Fox" in system_prompt
    assert "ONE short, warm, genuine" in system_prompt
    assert messages == [{"role": "user", "content": "The story just ended."}]


async def test_story_opening_invitation_blocks_unsafe_model_output():
    llm = FakeLanguageModelBackend(reply="That's a damn good story.")
    service = ConversationService(llm)

    result = await service.story_opening_invitation(story_transcript="...")

    assert result.blocked is True
    assert result.category == SafetyCategory.PROFANITY


def test_repeat_after_me_echoes_clean_text_without_calling_llm():
    llm = FakeLanguageModelBackend(reply="should never be used")
    service = ConversationService(llm)

    result = service.repeat_after_me("I love dinosaurs")

    assert result.blocked is False
    assert result.text == "I love dinosaurs"
    assert llm.calls == []


def test_repeat_after_me_declines_profanity_without_echoing_it():
    llm = FakeLanguageModelBackend(reply="should never be used")
    service = ConversationService(llm)

    result = service.repeat_after_me("say damn")

    assert result.blocked is True
    assert result.category == SafetyCategory.PROFANITY
    assert "damn" not in result.text.lower()
    assert llm.calls == []


async def test_summarize_session_returns_the_summary_text():
    llm = FakeLanguageModelBackend(reply="irrelevant for the main llm")
    summarizer = FakeLanguageModelBackend(reply="Learned addition. Read a story about a fox.")
    service = ConversationService(llm, summarizer_llm=summarizer)

    summary = await service.summarize_session(
        ["user: 2 plus 2 is 4", "assistant: Wow, neat!"]
    )

    assert summary == "Learned addition. Read a story about a fox."
    assert llm.calls == []  # must use the summarizer backend, not the main one
    assert summarizer.calls[0][1] == SESSION_SUMMARY_SYSTEM_PROMPT


async def test_summarize_session_returns_empty_string_for_empty_transcript():
    summarizer = FakeLanguageModelBackend(reply="should never be used")
    service = ConversationService(FakeLanguageModelBackend(reply="x"), summarizer_llm=summarizer)

    summary = await service.summarize_session([])

    assert summary == ""
    assert summarizer.calls == []


async def test_summarize_session_returns_empty_string_for_nothing_worth_keeping():
    summarizer = FakeLanguageModelBackend(reply="NOTHING")
    service = ConversationService(FakeLanguageModelBackend(reply="x"), summarizer_llm=summarizer)

    summary = await service.summarize_session(["user: hi", "assistant: hi!"])

    assert summary == ""


async def test_welcome_back_greeting_uses_summarizer_backend_and_screens_output():
    llm = FakeLanguageModelBackend(reply="irrelevant for the main llm")
    summarizer = FakeLanguageModelBackend(reply="Hi Anna! Last time we learned addition!")
    service = ConversationService(llm, summarizer_llm=summarizer)

    result = await service.welcome_back_greeting("Anna", "Learned addition.")

    assert result.blocked is False
    assert result.text == "Hi Anna! Last time we learned addition!"
    assert llm.calls == []


async def test_welcome_back_greeting_blocks_unsafe_summarizer_output():
    llm = FakeLanguageModelBackend(reply="irrelevant")
    summarizer = FakeLanguageModelBackend(reply="Don't tell your mom about this.")
    service = ConversationService(llm, summarizer_llm=summarizer)

    result = await service.welcome_back_greeting("Anna", "some summary")

    assert result.blocked is True
    assert result.category == SafetyCategory.PARENT_SECRECY


def test_default_summarizer_llm_is_the_main_llm_when_not_given():
    llm = FakeLanguageModelBackend(reply="x")
    service = ConversationService(llm)

    assert service._summarizer_llm is llm


async def test_classify_intent_returns_a_known_label():
    llm = FakeLanguageModelBackend(reply="STORY")
    service = ConversationService(llm)

    label = await service.classify_intent("can you tell me something fun")

    assert label == "STORY"
    assert llm.calls[0][1] == INTENT_CLASSIFIER_SYSTEM_PROMPT


async def test_classify_intent_strips_and_uppercases_the_reply():
    llm = FakeLanguageModelBackend(reply="  song \n")
    service = ConversationService(llm)

    assert await service.classify_intent("sing something nice") == "SONG"


async def test_classify_intent_returns_none_for_unrecognized_reply():
    llm = FakeLanguageModelBackend(reply="NONE")
    service = ConversationService(llm)

    assert await service.classify_intent("just chatting") is None


async def test_classify_intent_returns_none_for_garbage_reply():
    llm = FakeLanguageModelBackend(reply="I'm not sure what you mean")
    service = ConversationService(llm)

    assert await service.classify_intent("hmm") is None


async def test_classify_intent_output_is_not_screened_through_check_speech():
    """Its output is never spoken, only used for routing -- unlike
    every other ConversationService method, it must not go through
    _screen()/check_speech() at all, even if the (never-spoken) label
    text were somehow unsafe."""
    llm = FakeLanguageModelBackend(reply="story")
    service = ConversationService(llm)

    label = await service.classify_intent("tell me a story")

    assert label == "STORY"  # plain string, not a ConversationResult


async def test_classify_intent_uses_classifier_llm_when_given():
    """Decision 0047: classify_intent() asks for exactly one word, so
    a caller that wants it tightly capped (max_tokens=10, temperature=0
    on the real OpenAI backend) passes a separate instance here rather
    than inheriting the main conversational llm's much larger budget."""
    main_llm = FakeLanguageModelBackend(reply="irrelevant -- must not be called")
    classifier_llm = FakeLanguageModelBackend(reply="SONG")
    service = ConversationService(main_llm, classifier_llm=classifier_llm)

    label = await service.classify_intent("play a song")

    assert label == "SONG"
    assert main_llm.calls == []
    assert len(classifier_llm.calls) == 1


async def test_classify_intent_defaults_to_the_main_llm_when_no_classifier_given():
    llm = FakeLanguageModelBackend(reply="CHAT")
    service = ConversationService(llm)

    label = await service.classify_intent("let's just talk")

    assert label == "CHAT"
    assert len(llm.calls) == 1


async def test_generate_decodable_book_uses_the_main_llm_and_returns_a_book():
    """Decision 0051: wires reading/book_generation.py's pure
    verifier-gated loop to this service's own llm, parsing its
    TITLE:/PAGE: reply format."""
    from companion_robot.reading.planner import select_objective
    from companion_robot.reading.schema import ReadingProfile

    llm = FakeLanguageModelBackend(reply="TITLE: The Cat\nPAGE: A cat sat.\nPAGE: A cat ran.")
    service = ConversationService(llm)
    objective = select_objective(ReadingProfile.new("child-1"))

    book = await service.generate_decodable_book(objective, interest="cats", age=6)

    assert book.title == "The Cat"
    assert book.pages == ["A cat sat.", "A cat ran."]
    assert len(llm.calls) == 1


async def test_generate_decodable_book_passes_source_passage_into_the_prompt():
    """Decision 0068: a parent-uploaded exercise's text, passed as
    source_passage, must reach the actual prompt sent to the LLM."""
    from companion_robot.reading.planner import select_objective
    from companion_robot.reading.schema import ReadingProfile

    llm = FakeLanguageModelBackend(reply="TITLE: The Rat\nPAGE: A rat sat.")
    service = ConversationService(llm)
    objective = select_objective(ReadingProfile.new("child-1"))

    await service.generate_decodable_book(
        objective, age=6, source_passage="A cat sat on a yellow mat."
    )

    _messages, system_prompt = llm.calls[0]
    assert "A cat sat on a yellow mat." in system_prompt


async def test_generate_comprehension_questions_parses_the_reply():
    llm = FakeLanguageModelBackend(
        reply="QUESTION: What does the bunny see?\nQUESTION: Where does it sit?"
    )
    service = ConversationService(llm)

    questions = await service.generate_comprehension_questions(
        "A bunny sees an apple and sits under a tree.", num_questions=2, age=6
    )

    assert questions == ["What does the bunny see?", "Where does it sit?"]
    assert len(llm.calls) == 1


async def test_generate_comprehension_questions_drops_an_unsafe_one():
    """Decision 0059: each candidate question is screened through
    check_speech() independently -- a flagged one is dropped, the
    safe ones still come back."""
    llm = FakeLanguageModelBackend(
        reply=(
            "QUESTION: What does the bunny see?\n"
            "QUESTION: This is a damn good story, right?\n"
            "QUESTION: Where does it sit?"
        )
    )
    service = ConversationService(llm)

    questions = await service.generate_comprehension_questions(
        "A bunny sees an apple and sits under a tree.", num_questions=3, age=6
    )

    assert questions == ["What does the bunny see?", "Where does it sit?"]


async def test_generate_comprehension_questions_returns_empty_when_all_unsafe():
    llm = FakeLanguageModelBackend(reply="QUESTION: This is a damn good story, right?")
    service = ConversationService(llm)

    questions = await service.generate_comprehension_questions(
        "A bunny sees an apple.", num_questions=1, age=6
    )

    assert questions == []


async def test_generate_word_family_parses_and_verifies_candidates():
    llm = FakeLanguageModelBackend(reply="WORD: cat\nWORD: sat\nWORD: bat")
    service = ConversationService(llm)

    words = await service.generate_word_family("mat", mastered_levels=["short_vowels"], age=6)

    assert words == ["cat", "sat", "bat"]
    assert len(llm.calls) == 1


async def test_generate_word_family_drops_a_candidate_with_a_different_rime():
    """Decision 0066: each candidate is verified against the target
    rime's exact grapheme sequence, not trusted on the model's say-so
    -- a candidate that doesn't actually share the rime is dropped."""
    llm = FakeLanguageModelBackend(reply="WORD: cat\nWORD: dog\nWORD: sat")
    service = ConversationService(llm)

    words = await service.generate_word_family("mat", mastered_levels=["short_vowels"], age=6)

    assert words == ["cat", "sat"]


async def test_generate_word_family_drops_the_original_word_itself():
    llm = FakeLanguageModelBackend(reply="WORD: mat\nWORD: cat")
    service = ConversationService(llm)

    words = await service.generate_word_family("mat", mastered_levels=["short_vowels"], age=6)

    assert words == ["cat"]


async def test_generate_word_family_returns_empty_when_word_has_no_rime():
    """A single-grapheme word (e.g. "a") has nothing left to vary --
    skipped before ever calling the LLM."""
    llm = FakeLanguageModelBackend(reply="WORD: should not be called")
    service = ConversationService(llm)

    words = await service.generate_word_family("a", mastered_levels=["short_vowels"], age=6)

    assert words == []
    assert len(llm.calls) == 0


async def test_generate_word_family_returns_empty_when_every_candidate_fails():
    llm = FakeLanguageModelBackend(reply="WORD: dog\nWORD: pig")
    service = ConversationService(llm)

    words = await service.generate_word_family("mat", mastered_levels=["short_vowels"], age=6)

    assert words == []


async def test_react_to_comprehension_answer_grounds_in_the_story():
    llm = FakeLanguageModelBackend(
        reply="STATUS: resolved\nSAY: Yes, exactly -- the bunny found a red apple!"
    )
    service = ConversationService(llm)

    result = await service.react_to_comprehension_answer(
        "A bunny sees a red apple.", "What does the bunny see?", "an apple", age=6
    )

    assert result.needs_retry is False
    assert result.text == "Yes, exactly -- the bunny found a red apple!"
    assert len(llm.calls) == 1
    # The prompt actually sent grounds the reaction in the real story text.
    assert "A bunny sees a red apple." in llm.calls[0][1]


async def test_react_to_comprehension_answer_requests_a_retry():
    """Decision 0062: before the last attempt, a wrong/incomplete
    answer asks for one retry instead of revealing the answer."""
    llm = FakeLanguageModelBackend(
        reply="STATUS: needs_retry\nSAY: Good try! What color was it?"
    )
    service = ConversationService(llm)

    result = await service.react_to_comprehension_answer(
        "A bunny sees a red apple.", "What does the bunny see?", "cheese", age=6,
        attempt_number=1, max_attempts=2,
    )

    assert result.needs_retry is True
    assert result.text == "Good try! What color was it?"


async def test_react_to_comprehension_answer_is_screened_like_any_other_reply():
    llm = FakeLanguageModelBackend(reply="STATUS: resolved\nSAY: That's a damn good answer!")
    service = ConversationService(llm)

    result = await service.react_to_comprehension_answer(
        "A bunny sees a red apple.", "What does the bunny see?", "an apple", age=6
    )

    assert result.needs_retry is False
    assert "damn" not in result.text


async def test_react_to_comprehension_answer_overrides_a_wrong_rejection_of_a_literal_answer():
    """Decision 0083, found live: the model rejected "red" for "What
    color is Dan's dog?" against a story that literally says "Dan has
    a red dog" -- with a clue that didn't even make sense -- then
    admitted on the final attempt it was right all along. A literal
    word match against the story text overrides the model's own
    needs_retry here, and its own (misleading) SAY text is replaced,
    not spoken."""
    llm = FakeLanguageModelBackend(
        reply=(
            "STATUS: needs_retry\n"
            "SAY: Great try! But remember, the dog has a color more commonly "
            "found in nature. What do you think?"
        )
    )
    service = ConversationService(llm)

    result = await service.react_to_comprehension_answer(
        "Dan has a red dog.", "What color is Dan's dog?", "red", age=6,
    )

    assert result.needs_retry is False
    assert "nature" not in result.text
    assert result.text == "Yes, that's it! Great job remembering that from the story."


async def test_react_to_comprehension_answer_overrides_a_resolved_reply_that_still_hedges():
    """Decision 0097, found live: a different shape of the same
    failure as decision 0083 -- the model marked STATUS "resolved"
    (so no retry was captured) for the answer "Log." against a story
    that literally says "A hen sat on a log," but its own SAY text
    still read like an unresolved clue ("...but think about what
    that something was again!"). needs_retry was already False here,
    so decision 0083's own override (gated on needs_retry) never
    fired -- this closes that gap by also checking whether the SAY
    text itself still sounds like a retry invitation."""
    llm = FakeLanguageModelBackend(
        reply=(
            "STATUS: resolved\n"
            "SAY: Great job! The hen did sit on something, but think about "
            "what that something was again!"
        )
    )
    service = ConversationService(llm)

    result = await service.react_to_comprehension_answer(
        "A hen sat on a log. A pig ran to the hen.", "What did the hen sit on?",
        "Log.", age=6,
    )

    assert result.needs_retry is False
    assert "think about" not in result.text
    assert result.text == "Yes, that's it! Great job remembering that from the story."


async def test_react_to_comprehension_answer_still_retries_a_genuinely_unrelated_answer():
    """The literal-match override must not swallow every retry -- an
    answer sharing no real word with the story still gets the
    model's own retry handling."""
    llm = FakeLanguageModelBackend(
        reply="STATUS: needs_retry\nSAY: Good try! What color was it?"
    )
    service = ConversationService(llm)

    result = await service.react_to_comprehension_answer(
        "Dan has a red dog.", "What color is Dan's dog?", "purple", age=6,
    )

    assert result.needs_retry is True
    assert result.text == "Good try! What color was it?"


async def test_react_to_comprehension_answer_never_retries_into_an_unsafe_reply():
    """Even if the model itself asked for a retry, a blocked reply
    forces needs_retry=False -- never loop on an unsafe response."""
    llm = FakeLanguageModelBackend(reply="STATUS: needs_retry\nSAY: That's a damn good try!")
    service = ConversationService(llm)

    result = await service.react_to_comprehension_answer(
        "A bunny sees a red apple.", "What does the bunny see?", "cheese", age=6
    )

    assert result.needs_retry is False
    assert "damn" not in result.text


async def test_generate_word_meaning_question_parses_and_returns_the_question():
    llm = FakeLanguageModelBackend(reply="QUESTION: What jumps over the log?")
    service = ConversationService(llm)

    question = await service.generate_word_meaning_question(
        "The frog jumps over the log.", "frog", age=6
    )

    assert question == "What jumps over the log?"


async def test_generate_word_meaning_question_returns_none_when_unsafe():
    llm = FakeLanguageModelBackend(reply="QUESTION: This is a damn good question, right?")
    service = ConversationService(llm)

    question = await service.generate_word_meaning_question(
        "The frog jumps over the log.", "frog", age=6
    )

    assert question is None


async def test_generate_word_meaning_question_returns_none_when_unparsed():
    llm = FakeLanguageModelBackend(reply="Sorry, I don't have a question.")
    service = ConversationService(llm)

    question = await service.generate_word_meaning_question(
        "The frog jumps over the log.", "frog", age=6
    )

    assert question is None
