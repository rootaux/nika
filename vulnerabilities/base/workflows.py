def _stage_name(stage_entry):
    return getattr(stage_entry, "__name__", None)


def _execute_stage(stage_entry, vulnerability, context, state):
    if hasattr(stage_entry, "__self__") and getattr(stage_entry, "__self__", None) is vulnerability:
        return stage_entry(context, state)

    return stage_entry(vulnerability, context, state)


def execute_stages(vulnerability, context, state):
    current_state = state

    for stage_entry in vulnerability.stages:
        stage_name = _stage_name(stage_entry)
        if stage_name and not vulnerability.should_run_stage(stage_entry, context):
            continue

        current_state = _execute_stage(stage_entry, vulnerability, context, current_state)

    return current_state
