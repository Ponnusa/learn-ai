"""Unit tests for companion_robot.reading.word_family -- rime
extraction, prompt building/parsing, and deterministic verification
(decision 0066). The actual LLM call lives in ConversationService; see
test_conversation_service.py."""
from companion_robot.reading.decodability import decompose
from companion_robot.reading.word_family import (
    build_family_prompt,
    extract_rime,
    parse_family_words,
    verify_family_word,
)


def test_extract_rime_splits_onset_and_rime():
    rime_spelling, rime_graphemes = extract_rime("mat")
    assert rime_spelling == "at"
    assert [g.grapheme for g in rime_graphemes] == ["a", "t"]


def test_extract_rime_rime_is_every_grapheme_after_the_first():
    rime_spelling, rime_graphemes = extract_rime("frog")
    assert rime_spelling == "rog"
    assert [g.grapheme for g in rime_graphemes] == ["r", "o", "g"]


def test_extract_rime_returns_none_for_a_single_grapheme_word():
    """"a" is one grapheme -- nothing left to vary once the onset is
    removed, so there's no rime to build a word family from."""
    assert extract_rime("a") is None


def test_build_family_prompt_embeds_the_word_and_rime():
    prompt = build_family_prompt("mat", "at", num_words=4)
    assert '"mat"' in prompt
    assert "-at" in prompt
    assert "WORD:" in prompt


def test_parse_family_words_reads_one_per_line():
    reply = "WORD: cat\nWORD: sat\nWORD: bat"
    assert parse_family_words(reply) == ["cat", "sat", "bat"]


def test_parse_family_words_ignores_blank_lines_and_is_case_insensitive():
    reply = "\nword: cat\n\n   \n"
    assert parse_family_words(reply) == ["cat"]


def test_parse_family_words_returns_empty_list_with_no_word_lines():
    assert parse_family_words("Sorry, I don't have any words.") == []


def test_verify_family_word_accepts_a_matching_rime():
    _, target_rime = extract_rime("mat")
    assert verify_family_word("cat", target_rime, ["short_vowels"]) is True
    assert verify_family_word("sat", target_rime, ["short_vowels"]) is True


def test_verify_family_word_rejects_a_different_rime():
    _, target_rime = extract_rime("mat")  # rime "at"
    assert verify_family_word("dog", target_rime, ["short_vowels"]) is False  # rime "og"


def test_verify_family_word_rejects_an_undecodable_candidate():
    """"chat" shares "mat"'s "at" rime, but its onset "ch" is a digraph
    -- undecodable if the child hasn't mastered digraphs yet."""
    _, target_rime = extract_rime("mat")
    assert decompose("chat").graphemes[0].grapheme == "ch"  # confirms the premise
    assert verify_family_word("chat", target_rime, ["short_vowels"]) is False


def test_verify_family_word_rejects_a_single_grapheme_candidate():
    _, target_rime = extract_rime("mat")
    assert verify_family_word("I", target_rime, ["short_vowels"]) is False
