"""Bedrock tool specifications and dispatch for the HR Copilot."""

from hr_app_backend.utils.errors import AppError

from . import intelligence, workflows

TOOL_SPECS = [
    {
        'toolSpec': {
            'name': 'query_absences',
            'description': (
                'Find employees who were marked absent at least N times in a month. '
                'Use for questions like "who has been absent more than 3 times this month".'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'min_count': {'type': 'integer', 'description': 'Minimum absence count. Default 3.'},
                        'month': {'type': 'string', 'description': 'Month as YYYY-MM. Defaults to the current month.'},
                        'department': {'type': 'string', 'description': 'Optional department name filter.'},
                    },
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'query_flight_risk',
            'description': (
                'Identify employees who may be at risk of leaving using attendance, leave, '
                'and performance signals. Use for "which employees are at risk of leaving".'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'department': {'type': 'string', 'description': 'Optional department name filter.'},
                    },
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'query_performance_drop',
            'description': (
                'Find employees whose attendance or review signals worsened over recent months. '
                'Use for "whose performance has dropped over the last 3 months".'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'months': {'type': 'integer', 'description': 'Lookback window in months. Default 3.'},
                        'department': {'type': 'string', 'description': 'Optional department name filter.'},
                    },
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'query_salary_reviews',
            'description': (
                'List employees whose hire anniversary is approaching and who are due for a salary review.'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'within_days': {'type': 'integer', 'description': 'Days until anniversary. Default 45.'},
                        'department': {'type': 'string', 'description': 'Optional department name filter.'},
                    },
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'simulate_payroll_increment',
            'description': (
                'Calculate how much monthly and annual payroll would increase if salaries '
                'are raised by a percent. Use for "how much will payroll increase if we give 10%".'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'percent': {'type': 'number', 'description': 'Increment percent, for example 10.'},
                        'department': {'type': 'string', 'description': 'Optional department name filter.'},
                    },
                    'required': ['percent'],
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'get_employee_review_context',
            'description': (
                'Load one employee\'s attendance, leave, and prior reviews so you can '
                'draft a performance review. Use before writing review text.'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string', 'description': 'Employee full or partial name.'},
                        'employee_id': {'type': 'string', 'description': 'Optional employee UUID or company employee ID.'},
                    },
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'search_employees',
            'description': 'Search employees by name, department, or employee ID.',
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'department': {'type': 'string'},
                        'employee_id': {'type': 'string'},
                    },
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'get_hr_insights',
            'description': (
                'Return organization-wide HR insights, alerts, and recommended actions '
                'across attendance, leave, performance, and payroll.'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'department': {'type': 'string', 'description': 'Optional department name filter.'},
                    },
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'create_review_cycle',
            'description': (
                'Create a performance review cycle for every active employee in a department, '
                'assign reviewers (managers), set a start date and deadline, and notify people. '
                'Call this only when the user clearly asked to create the cycle.'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'department': {'type': 'string', 'description': 'Department name, for example Engineering.'},
                        'start_date': {'type': 'string', 'description': 'ISO date YYYY-MM-DD.'},
                        'cycle_name': {'type': 'string', 'description': 'Optional review cycle title.'},
                        'due_days': {'type': 'integer', 'description': 'Days after start until the deadline. Default 30.'},
                        'notify': {'type': 'boolean', 'description': 'Whether to notify employees and managers. Default true.'},
                    },
                    'required': ['department', 'start_date'],
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'save_performance_review',
            'description': (
                'Save a drafted performance review for one employee. Call after you have written '
                'the review text and the user asked to create or save it.'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string', 'description': 'Employee name.'},
                        'review_text': {'type': 'string', 'description': 'The full review draft to store.'},
                        'cycle_name': {'type': 'string'},
                        'employee_id': {'type': 'string'},
                    },
                    'required': ['name', 'review_text'],
                }
            },
        }
    },
    {
        'toolSpec': {
            'name': 'notify_employees',
            'description': (
                'Send an inbox notification to employees in a department or a named list. '
                'Call only when the user asked to notify or remind people.'
            ),
            'inputSchema': {
                'json': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'body': {'type': 'string'},
                        'department': {'type': 'string'},
                        'names': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'Employee names to notify.',
                        },
                    },
                    'required': ['title', 'body'],
                }
            },
        }
    },
]


def _clean_input(payload):
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items() if value not in (None, '')}


def execute_tool(name, payload, user):
    data = _clean_input(payload)
    handlers = {
        'query_absences': lambda: intelligence.query_absences(user, **data),
        'query_flight_risk': lambda: intelligence.query_flight_risk(user, **data),
        'query_performance_drop': lambda: intelligence.query_performance_drop(user, **data),
        'query_salary_reviews': lambda: intelligence.query_salary_reviews(user, **data),
        'simulate_payroll_increment': lambda: intelligence.simulate_payroll_increment(user, **data),
        'get_employee_review_context': lambda: intelligence.get_employee_review_context(user, **data),
        'search_employees': lambda: intelligence.search_employees(user, **data),
        'get_hr_insights': lambda: intelligence.get_hr_insights(user, **data),
        'create_review_cycle': lambda: workflows.create_review_cycle(user, **data),
        'save_performance_review': lambda: workflows.save_performance_review(user, **data),
        'notify_employees': lambda: workflows.notify_employees(user, **data),
    }
    handler = handlers.get(name)
    if handler is None:
        return {'error': f'Unknown tool: {name}'}, None
    try:
        result = handler()
    except (TypeError, ValueError) as exc:
        return {'error': f'Invalid arguments for {name}: {exc}'}, None
    except AppError as exc:
        return {'error': exc.message}, None

    action = result.pop('action', None) if isinstance(result, dict) else None
    return result, action
