"""Import every ORM model so Base.metadata is complete (Alembic, tests)."""

from app.llm import models as _llm  # noqa: F401
from app.modules.assessment import models as _assessment  # noqa: F401
from app.modules.audit import models as _audit  # noqa: F401
from app.modules.curriculum import models as _curriculum  # noqa: F401
from app.modules.enrollment import models as _enrollment  # noqa: F401
from app.modules.evaluation import models as _evaluation  # noqa: F401
from app.modules.events import models as _events  # noqa: F401
from app.modules.external_training import models as _external_training  # noqa: F401
from app.modules.identity import models as _identity  # noqa: F401
from app.modules.knowledge import models as _knowledge  # noqa: F401
from app.modules.learn import models as _learn  # noqa: F401
from app.modules.mastery import models as _mastery  # noqa: F401
from app.modules.memory import models as _memory  # noqa: F401
from app.modules.mistakes import models as _mistakes  # noqa: F401
from app.modules.planner import models as _planner  # noqa: F401
from app.modules.safety import models as _safety  # noqa: F401
from app.modules.studies import models as _studies  # noqa: F401
from app.modules.tutoring import models as _tutoring  # noqa: F401
