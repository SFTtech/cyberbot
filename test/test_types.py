from cyberbot.types import Err, Ok, Result


def get_result(val, expected) -> Result[str, str]:
    if val == expected:
        return Ok("yeey")

    return Err("nope")


def check_result_match(val, type):
    assert isinstance(val, type)
    match val:
        case Ok(v):
            assert v == "yeey"

        case Err(e):
            assert e == "nope"

        case _:
            raise ValueError("unexpected")


def test_result_err():
    check_result_match(get_result(1, 2), Err)


def test_result_ok():
    check_result_match(get_result(1, 1), Ok)
