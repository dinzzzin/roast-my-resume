"""Expected: cyclomatic_complexity
Eligibility rules written as one tangle of and/or without parentheses."""


def is_eligible(age, income, student, veteran, state, score):
    if age >= 18 and income < 40000 or student and age < 26 or veteran:
        if state == "NY" or state == "NJ" or state == "CT" and score > 600:
            return True
        elif score > 700 and income < 60000 or veteran and score > 550:
            return True
    if age > 65 and income < 30000 or age > 70:
        return score > 500 or veteran
    return False
