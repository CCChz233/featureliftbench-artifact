from featurelifted import Revision, RevisionMap


def test_heads_for_linear_revision_map():
    revisions = [Revision("a", None), Revision("b", "a")]
    revmap = RevisionMap(revisions)

    assert revmap.get_current_head() == "b"
    assert revmap.get_heads() == ["b"]
    assert revmap.bases == ("a",)
    assert revmap.get_revision("a").revision == "a"


def test_merge_revision_removes_branch_heads():
    revisions = [
        Revision("base", None),
        Revision("left", "base"),
        Revision("right", "base"),
        Revision("merge", ("left", "right")),
    ]
    revmap = RevisionMap(revisions)

    assert revmap.get_heads() == ["merge"]
    assert revmap.get_revision("merge").is_merge_point
    assert revmap.get_revision("base").is_branch_point


def test_iterate_revisions_walks_down_revision_chain():
    revmap = RevisionMap([Revision("a", None), Revision("b", "a"), Revision("c", "b")])

    assert [revision.revision for revision in revmap.iterate_revisions("c", "a")] == ["c", "b"]
