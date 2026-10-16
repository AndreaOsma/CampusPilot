import pytest

from app.grades import ActivityData, EvalData, GroupData, career_average, evaluate


def fp(grades_pec, grades_pr):
    """FP: 30 % PEC (mín. 4) + 70 % PR (mín. 5), cada grupo con sus actividades a igual peso."""
    acts = [ActivityData(i, 1, grade=g) for i, g in enumerate(grades_pec, start=1)]
    acts += [ActivityData(100 + i, 2, grade=g) for i, g in enumerate(grades_pr, start=1)]
    return EvalData(groups=[GroupData(1, "PEC", 30, 4), GroupData(2, "PR", 70, 5)], activities=acts)


def test_weighted_final_and_pass():
    r = evaluate(fp([8, 6], [7, 7]))
    assert r.final == pytest.approx(0.3 * 7 + 0.7 * 7)
    assert r.passed is True
    assert r.pending == 0
    assert r.needed is None


def test_weighted_minimum_fails_even_with_good_average():
    r = evaluate(fp([10, 10], [4, 4.5]))
    assert r.final is not None and r.final > 5
    assert r.passed is False
    assert any("PR" in reason for reason in r.reasons)


def test_needed_uniform_grade_respects_group_minimum():
    # PEC ya en 10; PR pendiente: la media llegaría a 5 con 2.86, pero el mínimo de PR es 5.
    r = evaluate(fp([10, 10], [None, None]))
    assert r.final is None and r.pending == 2
    assert r.needed == 5.0


def test_needed_respects_target():
    r = evaluate(fp([5, 5], [None]), target=7)
    # 0.3*5 + 0.7*x >= 7  →  x >= 7.857…
    assert r.needed == 7.86


def test_impossible_target():
    r = evaluate(fp([0, 0], [None]), target=9)
    assert r.achievable is False and r.needed is None


def test_hypothetical_grades_complete_the_subject():
    data = fp([6], [None])
    r = evaluate(data, {101: 8})
    assert r.final == pytest.approx(0.3 * 6 + 0.7 * 8) and r.passed is True


def test_max_grade_is_normalized():
    data = EvalData(groups=[GroupData(1, "Todo", 100)], activities=[ActivityData(1, 1, grade=45, max_grade=50)])
    assert evaluate(data).final == pytest.approx(9)


def mates(ec, pf):
    acts = [ActivityData(1, 1, grade=ec)]
    if pf != "group-empty":
        acts.append(ActivityData(2, 2, grade=pf))
    return EvalData(
        model="ec_pf",
        groups=[GroupData(1, "EC", 50, role="ec"), GroupData(2, "PF", 50, 4, role="pf")],
        activities=acts,
        ec_pass=5,
        pf_min=4,
    )


def test_ec_pf_weighted_when_both_pass():
    r = evaluate(mates(7, 6))
    assert r.final == 6.5 and r.passed is True


def test_ec_failed_final_is_ec():
    r = evaluate(mates(4, None))
    assert r.final == 4 and r.passed is False


def test_pf_below_minimum_final_is_pf():
    r = evaluate(mates(9, 3.5))
    assert r.final == 3.5 and r.passed is False


def test_ec_pf_needed_in_pf():
    # EC 6: 0.5*6 + 0.5*x >= 5 → x >= 4 (y el mínimo de la PF también es 4).
    assert evaluate(mates(6, None)).needed == 4.0
    # EC 9: la media pediría 1, pero manda el mínimo de 4.
    assert evaluate(mates(9, None)).needed == 4.0
    # Grupo PF sin actividades (estructura aún desconocida): cuenta como una pieza pendiente.
    r = evaluate(mates(6, "group-empty"))
    assert r.pending == 1 and r.needed == 4.0


def test_zero_weight_activities_do_not_count():
    data = EvalData(
        groups=[GroupData(1, "EC", 100)],
        activities=[ActivityData(1, 1, weight=0, grade=None), ActivityData(2, 1, grade=8)],
    )
    r = evaluate(data)
    assert r.final == 8 and r.pending == 0


def test_career_average():
    assert career_average([(6, 8), (6, 6), (12, None)]) == 7
    assert career_average([(6, None)]) is None
