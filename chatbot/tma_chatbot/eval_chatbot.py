"""Evaluation F6 (reponses), F7 (sources) et F8 (temps)."""

import statistics

from llm import chat

CASES = [
    ("Quels sont les 3 tickets les plus chronophages ?", "top_tickets_chronophages", None),
    ("Quels sont les incidents les plus frequents sur les trois derniers mois ?", "familles_recurrentes", None),
    ("Quelle famille pese le plus dans la charge ?", "familles_recurrentes", None),
    ("Fais-moi la synthese hebdomadaire.", "synthese_hebdo", None),
    ("Donne-moi le detail du ticket TMA-1000.", "detail_ticket", "TMA-1000"),
    ("Quelle est la meteo a Brest ?", None, None),
]


def _source_ids(value) -> set[str]:
    if isinstance(value, dict):
        result = set(value.get("tickets_sources", []))
        for nested in value.values():
            result.update(_source_ids(nested))
        return result
    if isinstance(value, list):
        result = set()
        for nested in value:
            result.update(_source_ids(nested))
        return result
    return set()


def main() -> None:
    correct_tools = 0
    cited_sources = 0
    durations = []
    for question, expected_tool, expected_text in CASES:
        answer, calls, duration = chat([{"role": "user", "content": question}])
        tool_names = [call["outil"] for call in calls]
        correct_tool = expected_tool in tool_names if expected_tool else not tool_names
        sources = set().union(*(_source_ids(call["resultat"]) for call in calls)) if calls else set()
        source_cited = not calls or any(ticket_id in answer for ticket_id in sources)
        expected_text_found = expected_text is None or expected_text in answer
        correct_tools += correct_tool
        cited_sources += source_cited and expected_text_found
        durations.append(duration)
        print(
            f"[{'OK' if correct_tool else 'KO'}] {question}\n"
            f"     outils={tool_names} sources_citees={source_cited} {duration:.1f}s"
        )

    count = len(CASES)
    print(
        f"\nBon outil : {correct_tools}/{count} | Sources citees : {cited_sources}/{count}"
        f" | Temps moyen : {statistics.mean(durations):.1f}s"
    )


if __name__ == "__main__":
    main()