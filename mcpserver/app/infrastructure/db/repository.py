"""
Deprecated module.

This file previously contained a legacy `AsyncSQLAlchemyCourseRepository` implementation
that depended on `CourseRepository` from `app.core.repositories`. The core interface has
been removed as part of dead code cleanup, and this module is intentionally left empty.

Any course-related persistence is out of scope for this service. If needed in the future,
introduce a new interface in `app/core/` and a matching implementation under
`app/infrastructure/db/` following the Clean Architecture patterns.
"""

# Intentionally empty.
