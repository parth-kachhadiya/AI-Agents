import time
from concurrent.futures import ThreadPoolExecutor
from shared_setup import Ask
from collections import Counter

# ----------------------< Parallel Executor >----------------------
def Parallel_Sectioning(topic : str):
    aspects = [
        "The main advantages.",
        "The main risks.",
        "A one-line verdict."
    ]

    with ThreadPoolExecutor() as pool:
        parts = list(pool.map(lambda a : Ask(f"Give {a} of {topic} in two sentences."), aspects))

    return "\n • ".join(parts)


def Parallel_Voting(question : str, n : int = 3):
    with ThreadPoolExecutor() as pool:
        answers = list(pool.map(
            lambda _ : Ask(f"Question : {question}., Reply with only either `yes` or `no`.", temperature = 0.1), range(n)
        ))

    answers = [a.strip().lower().rstrip(".") for a in answers]

    return Counter(answers).most_common(1)[0]

# ----------------------< Sequential Executor >----------------------
def Sequential_Sectioning(topic : str):
    aspects = [
        "The main advantages.",
        "The main risks.",
        "A one-line verdict."
    ]

    responses = []

    for aspect in aspects:
        responses.append(Ask(f"Given {aspect} of {topic} in two sentences."))

    return "\n • ".join(responses)

def Sequential_Voting(question : str, n : int = 3):
    answers = []
    for _ in range(n):
        vote = Ask(f"Question : {question}., Reply with only either `yes` or `no`.", temperature=0.1).strip().lower().rstrip(".")
        answers.append(vote)

    return Counter(answers).most_common(1)[0]


# ----------------------< Output Formatting Helpers >----------------------
WIDTH = 72

def banner(title : str):
    print("\n" + "=" * WIDTH)
    print(title.center(WIDTH))
    print("=" * WIDTH)

def section(title : str):
    print("\n" + "-" * 20 + f"[{title}]" + "-" * 20)

def show_sectioning(text : str):
    for line in text.split("\n"):
        line = line.strip()
        if line:
            print("  " + (line if line.startswith(("•", "-")) else "• " + line))

def show_voting(result : tuple, n : int):
    answer, count = result
    print(f"  Answer : {answer.upper()}")
    print(f"  Votes  : {count}/{n}")

def timed(func, *args):
    start = time.perf_counter()
    result = func(*args)
    return result, time.perf_counter() - start


# ----------------------< Run Everything >----------------------
TOPIC = "AGI"
QUESTION = "Does cow has 4 legs.?"
N_VOTES = 3

banner("SERIAL vs PARALLEL EXECUTION")

# ---- Serial ----
section("SERIAL : Sectioning")
response_a, t_serial_sec = timed(Sequential_Sectioning, TOPIC)
show_sectioning(response_a)

section("SERIAL : Voting")
response_b, t_serial_vote = timed(Sequential_Voting, QUESTION, N_VOTES)
show_voting(response_b, N_VOTES)

# ---- Parallel ----
section("PARALLEL : Sectioning")
response_c, t_par_sec = timed(Parallel_Sectioning, TOPIC)
show_sectioning(response_c)

section("PARALLEL : Voting")
response_d, t_par_vote = timed(Parallel_Voting, QUESTION, N_VOTES)
show_voting(response_d, N_VOTES)

# ---- Timing Summary ----
total_serial = t_serial_sec + t_serial_vote
total_parallel = t_par_sec + t_par_vote

banner("TIME TAKEN (seconds)")
print(f"{'Task':<20}{'Serial':>14}{'Parallel':>14}{'Speed-up':>14}")
print("-" * WIDTH)
for name, s, p in [
    ("Sectioning", t_serial_sec, t_par_sec),
    ("Voting", t_serial_vote, t_par_vote),
    ("TOTAL", total_serial, total_parallel),
]:
    speedup = f"{s / p:.2f}x" if p > 0 else "-"
    print(f"{name:<20}{s:>13.2f}s{p:>13.2f}s{speedup:>14}")
print("=" * WIDTH)