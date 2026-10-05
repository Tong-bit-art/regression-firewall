def change_of(changes, category, path=None):
    for change in changes:
        if change.category == category and (path is None or change.path == path):
            return change
    raise AssertionError(
        f"no change category={category} path={path} in "
        f"{[(c.category, c.path) for c in changes]}"
    )
