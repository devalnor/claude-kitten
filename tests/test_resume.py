from claude_kitten.__main__ import _is_resume


def test_detect_continue_flag():
    assert _is_resume(["--continue"]) is True
    assert _is_resume(["-c"]) is True


def test_detect_resume_flag():
    assert _is_resume(["--resume"]) is True


def test_no_resume_flag():
    assert _is_resume([]) is False
    assert _is_resume(["-p", "hello"]) is False
    assert _is_resume(["--model", "opus"]) is False
