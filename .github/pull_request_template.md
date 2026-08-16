<!--
Open a pull request only after agreement in an issue. Do not include manuscripts, returned Word
reviews, credentials, private templates, unpublished data, or other confidential material.
-->

## Agreed issue

Closes #

## Summary and user impact

Describe what changed, why it is needed, and the observable effect for users.

## Change type

- [ ] Technical workflow or code
- [ ] Tests
- [ ] Documentation
- [ ] Manuscript or scientific content, reviewed separately and explicitly

## Validation

- [ ] `uv run paperflow doctor`
- [ ] `uv run ruff check .`
- [ ] `uv run pytest`
- [ ] `uv run paperflow build`
- [ ] I listed any check that was not run and explained why below.

## Safety and review boundaries

- [ ] This pull request contains no generated DOCX, local configuration, reviewer material,
      credentials, private paths, confidential templates, or unpublished data.
- [ ] Technical and manuscript-content changes are separated or clearly justified.
- [ ] No scientific claim, citation key, figure number, author data, or quantitative result was
      silently changed.
- [ ] Documentation and tests cover the user-visible change where applicable.

## Checks not run or additional context

State any limitations, follow-up work, or review focus here.
