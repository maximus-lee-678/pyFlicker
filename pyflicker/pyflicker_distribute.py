def get_even_plan(values_count, concurrency_target, maximum_tasks_per_query) -> list[int]:
    """
    | Distributes data evenly (e.g. [101, 101, 100, 100, 100] for 502 parameters).
    | Usually paired with safe_transaction_multithread().
    | Ensures no value exceeds maximum_tasks_per_query, and that the number of parts is at most concurrency_target.

    :param int values_count: total number of parameters to distribute
    :param int concurrency_target: target number of concurrent threads to use
    :param int maximum_tasks_per_query: maximum number of parameters to put into each query

    :return: list[int]
    """

    if values_count <= 0:
        return []

    # Ensure we have enough parts so no value exceeds y
    concurrency_target = max(concurrency_target, -(-values_count // maximum_tasks_per_query))  # ceiling division

    base = values_count // concurrency_target
    remainder = values_count % concurrency_target

    # Distribute the remainder across the first few elements
    result = [base + 1] * remainder + [base] * (concurrency_target - remainder)

    while 0 in result:
        result.remove(0)

    return result


def form_query_list_from_plan(query_plan: list[int], formattable_query: str, values_strings: list[str]) -> list[str]:
    """
    | Substitutes a list of parameters into a new list containing formatted queries based on a query plan.
    | The field substituted into the formattable_query must be {values_strings}

    :param list[int] query_plan: list of integers representing the number of parameters to put into each query
    :param string formattable_query: query to substitute parameters into (must have {values_strings} where parameters are to be placed)
    :param list[str] values_strings: list of value strings to substitute into {values_strings} in formattable_query

    :return: list[str]
    """

    fragmented_queries = []
    query_index = 0

    for query_count in query_plan:
        if query_count == 0:
            continue

        fragmented_queries.append(
            formattable_query.format(values_strings=",".join(param for param in values_strings[query_index:query_index + query_count]))
        )
        query_index += query_count

    return fragmented_queries
