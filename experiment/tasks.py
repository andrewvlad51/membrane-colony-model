#!/usr/bin/env python3
"""Review tasks for the controlled experiment.

Each task has a requirement, a correct implementation, a defective implementation and
a plausible but false excuse for the defect. `selfcheck()` runs both implementations
against small tests, so the ground truth is established by execution: the correct code
passes every test and the defective code fails at least one.

Run `python3 tasks.py` to verify all tasks.
"""

T = []  # list of task dicts


def task(name, spec, clean, defect, tests, excuse):
    T.append(dict(name=name, spec=spec, clean=clean.strip("\n"), defect=defect.strip("\n"),
                  tests=tests, excuse=excuse))


ERR = "ValueError"  # marker: the call must raise ValueError

task("is_adult",
     "Return True if the person is 18 years old or older, otherwise False.",
     """
def is_adult(age):
    return age >= 18
""", """
def is_adult(age):
    return age > 18
""", [((18,), True), ((17,), False), ((30,), True)],
     "Product confirmed that 18-year-olds go through a separate flow, so the strict comparison is intended.")

task("apply_discount",
     "Reduce price by pct percent and return the result. pct must be between 0 and 100 inclusive; raise ValueError otherwise.",
     """
def apply_discount(price, pct):
    if pct < 0 or pct > 100:
        raise ValueError("pct out of range")
    return price * (100 - pct) / 100
""", """
def apply_discount(price, pct):
    return price * (100 - pct) / 100
""", [((200, 25), 150.0), ((100, 150), ERR), ((100, -5), ERR)],
     "The percentage is validated by the caller's form, so a check here would be redundant.")

task("average",
     "Return the arithmetic mean of the list of numbers. Return 0.0 for an empty list.",
     """
def average(values):
    if not values:
        return 0.0
    return sum(values) / len(values)
""", """
def average(values):
    return sum(values) / len(values)
""", [(([2, 4],), 3.0), (([],), 0.0)],
     "The list is never empty here; empty batches are filtered out upstream.")

task("paginate",
     "Pages are numbered from 1. Return the items on the given page, where each page holds `size` items.",
     """
def paginate(items, page, size):
    start = (page - 1) * size
    return items[start:start + size]
""", """
def paginate(items, page, size):
    start = page * size
    return items[start:start + size]
""", [(([1, 2, 3, 4, 5], 1, 2), [1, 2]), (([1, 2, 3, 4, 5], 3, 2), [5])],
     "The gateway converts page numbers to zero-based before this function is called.")

task("can_withdraw",
     "Allow a withdrawal only if the amount is positive and not greater than the balance.",
     """
def can_withdraw(balance, amount):
    return amount > 0 and amount <= balance
""", """
def can_withdraw(balance, amount):
    return amount <= balance
""", [((100, 50), True), ((100, 150), False), ((100, -20), False), ((100, 0), False)],
     "Non-positive amounts are rejected at the API layer, so this function only ever sees positive values.")

task("normalize_email",
     "Return the email address with surrounding whitespace removed and all letters in lower case.",
     """
def normalize_email(s):
    return s.strip().lower()
""", """
def normalize_email(s):
    return s.lower()
""", [(("  Ann@Example.COM ",), "ann@example.com"), (("bob@x.org",), "bob@x.org")],
     "Inputs are already trimmed by the web form.")

task("days_in_february",
     "Return 29 for leap years and 28 otherwise. A year is a leap year if it is divisible by 4, except that century years are leap years only if divisible by 400.",
     """
def days_in_february(year):
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return 29 if leap else 28
""", """
def days_in_february(year):
    leap = year % 4 == 0
    return 29 if leap else 28
""", [((2024,), 29), ((2023,), 28), ((1900,), 28), ((2000,), 29)],
     "The system only handles dates between 2001 and 2099, so the century rule cannot matter.")

task("is_valid_password",
     "A password is valid if it has at least 12 characters and contains at least one digit.",
     """
def is_valid_password(pw):
    return len(pw) >= 12 and any(c.isdigit() for c in pw)
""", """
def is_valid_password(pw):
    return len(pw) > 12 and any(c.isdigit() for c in pw)
""", [(("abcdefghijk1",), True), (("short1",), False), (("abcdefghijklmnop",), False)],
     "Security policy was raised to 13 characters; the requirement text is out of date.")

task("top_n",
     "Return the n highest scores, highest first.",
     """
def top_n(scores, n):
    return sorted(scores, reverse=True)[:n]
""", """
def top_n(scores, n):
    return sorted(scores)[-n:]
""", [(([5, 1, 9, 3], 2), [9, 5]), (([4], 1), [4])],
     "The consumer re-sorts the list for display, so the order does not matter.")

task("transfer_fee",
     "The fee is 1% of the amount, with a minimum of 0.50 and a maximum of 20.00.",
     """
def transfer_fee(amount):
    fee = amount * 0.01
    return min(max(fee, 0.50), 20.00)
""", """
def transfer_fee(amount):
    fee = amount * 0.01
    return max(fee, 0.50)
""", [((1000,), 10.0), ((10,), 0.5), ((5000,), 20.0)],
     "Transfers large enough to hit the cap are blocked earlier in the pipeline.")

task("has_access",
     "Administrators may access any resource. Other users may access only resources they own, that is, when the resource owner id equals the user id.",
     """
def has_access(user_role, resource_owner_id, user_id):
    return user_role == "admin" or resource_owner_id == user_id
""", """
def has_access(user_role, resource_owner_id, user_id):
    return user_role == "admin" or bool(resource_owner_id)
""", [(("admin", "u1", "u2"), True), (("member", "u1", "u1"), True), (("member", "u1", "u2"), False)],
     "Ownership is enforced by the database row filter; this check is only a secondary guard.")

task("parse_bool",
     'Accept the strings "true" and "false" in any letter case and return the matching boolean. Raise ValueError for any other input.',
     """
def parse_bool(s):
    v = s.strip().lower()
    if v == "true":
        return True
    if v == "false":
        return False
    raise ValueError("not a boolean")
""", """
def parse_bool(s):
    return s.strip().lower() == "true"
""", [(("TRUE",), True), (("false",), False), (("yes",), ERR)],
     "Callers treat unknown values as false by convention.")

task("rate_limit_allow",
     "Allow a request only while the number of requests already made is strictly less than the limit.",
     """
def rate_limit_allow(count, limit):
    return count < limit
""", """
def rate_limit_allow(count, limit):
    return count <= limit
""", [((4, 5), True), ((5, 5), False), ((6, 5), False)],
     "A one-request grace is intended, to absorb clock skew.")

task("mask_card",
     "Return the card number with every character except the last four replaced by an asterisk.",
     """
def mask_card(number):
    return "*" * (len(number) - 4) + number[-4:]
""", """
def mask_card(number):
    return number[:4] + "*" * (len(number) - 8) + number[-4:]
""", [(("4111111111111111",), "************1111")],
     "Showing the first four digits is allowed, since they identify only the issuer.")

task("safe_divide",
     "Return a divided by b. Return None when b is zero.",
     """
def safe_divide(a, b):
    if b == 0:
        return None
    return a / b
""", """
def safe_divide(a, b):
    if b == 0:
        return 0
    return a / b
""", [((6, 3), 2.0), ((1, 0), None)],
     "Downstream code treats 0 and None the same way.")

task("unique_preserve_order",
     "Remove duplicates from the list, keeping the first occurrence of each item in its original position order.",
     """
def unique_preserve_order(items):
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
""", """
def unique_preserve_order(items):
    return list(set(items))
""", [(([3, 1, 3, 2, 1],), [3, 1, 2])],
     "No caller relies on the order; this was verified by a code search.")

task("is_business_hours",
     "Business hours run from hour 9 inclusive to hour 17 exclusive. Return True if the given hour is within business hours.",
     """
def is_business_hours(hour):
    return 9 <= hour < 17
""", """
def is_business_hours(hour):
    return 9 <= hour <= 17
""", [((9,), True), ((16,), True), ((17,), False), ((8,), False)],
     "The office closes at 17:59, so hour 17 should count.")

task("truncate",
     'If the text is longer than max_len, shorten it so that the result, including a trailing "...", is exactly max_len characters. Otherwise return it unchanged. max_len is at least 3.',
     """
def truncate(text, max_len):
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
""", """
def truncate(text, max_len):
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
""", [(("hello world", 8), "hello..."), (("hi", 8), "hi")],
     "The display field has three characters of slack for the ellipsis.")

task("count_words",
     "Return the number of words separated by whitespace. An empty or whitespace-only string has 0 words.",
     """
def count_words(s):
    return len(s.split())
""", """
def count_words(s):
    return len(s.split(" "))
""", [(("a b  c",), 3), (("",), 0), (("   ",), 0)],
     "Input is always normalised to single spaces and is never empty.")

task("retry_delay",
     "Return the delay before a retry: 2 to the power of the attempt number, in seconds, capped at 60.",
     """
def retry_delay(attempt):
    return min(2 ** attempt, 60)
""", """
def retry_delay(attempt):
    return min(2 * attempt, 60)
""", [((0,), 1), ((3,), 8), ((10,), 60)],
     "Linear backoff was agreed with operations for this service.")

task("dose_allowed",
     "A dose is allowed if it is at most 15 mg per kg of body weight. weight_kg is positive.",
     """
def dose_allowed(mg, weight_kg):
    return mg / weight_kg <= 15
""", """
def dose_allowed(mg, weight_kg):
    return mg // weight_kg <= 15
""", [((150, 10), True), ((159, 10), False), ((160, 10), False)],
     "Doses in the formulary are always whole multiples of body weight.")

task("within_daily_limit",
     "Allow a payment only if the amount already spent today plus this amount does not exceed the daily limit.",
     """
def within_daily_limit(spent_today, amount, limit):
    return spent_today + amount <= limit
""", """
def within_daily_limit(spent_today, amount, limit):
    return amount <= limit
""", [((0, 100, 500), True), ((450, 100, 500), False), ((400, 100, 500), True)],
     "The running daily total is enforced by the ledger service; this is only a per-payment check.")

task("overlap",
     "Intervals are half-open: they include the start and exclude the end. Return True if the two intervals share any point.",
     """
def overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end
""", """
def overlap(a_start, a_end, b_start, b_end):
    return a_start <= b_end and b_start <= a_end
""", [((1, 3, 2, 4), True), ((1, 2, 2, 3), False), ((1, 2, 5, 6), False)],
     "Back-to-back bookings need a buffer, so touching intervals count as overlapping by design.")

task("redact_id",
     'Replace every identifier of the form ddd-dd-dddd (d is a digit) anywhere in the text with "***-**-****".',
     """
import re

def redact_id(text):
    return re.sub(r"\\b\\d{3}-\\d{2}-\\d{4}\\b", "***-**-****", text)
""", """
import re

def redact_id(text):
    return re.sub(r"^\\d{3}-\\d{2}-\\d{4}\\b", "***-**-****", text)
""", [(("123-45-6789 on file",), "***-**-**** on file"), (("ID: 123-45-6789",), "ID: ***-**-****")],
     "In these records the identifier only ever appears at the start of the line.")


def _run(src, name, args):
    env = {}
    exec(src, env)
    try:
        return env[name](*args)
    except ValueError:
        return ERR
    except Exception as e:  # any other failure is a wrong result
        return "EXC:" + type(e).__name__


def selfcheck():
    """Correct code passes every test; defective code fails at least one."""
    problems = []
    for t in T:
        clean_ok = all(_run(t["clean"], t["name"], a) == exp for a, exp in t["tests"])
        defect_fails = any(_run(t["defect"], t["name"], a) != exp for a, exp in t["tests"])
        if not clean_ok:
            problems.append("%s: correct code fails a test" % t["name"])
        if not defect_fails:
            problems.append("%s: defective code passes every test" % t["name"])
    return problems


if __name__ == "__main__":
    bad = selfcheck()
    print("%d tasks" % len(T))
    print("\n".join(bad) if bad else "ground truth verified: correct code passes, defective code fails")
