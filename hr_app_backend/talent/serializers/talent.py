def serialize_job(job):
    return {
        'id': job.id,
        'title': job.title,
        'department': job.department,
        'location': job.location,
        'type': job.type,
        'status': job.status,
        'applicants': job.applicants,
        'postedDate': job.posted_date.isoformat(),
        'description': job.description or None,
    }


def serialize_onboarding(plan):
    return {
        'id': str(plan.id),
        'employeeName': plan.employee_name,
        'startDate': plan.start_date.isoformat(),
        'owner': plan.owner,
        'status': plan.status,
        'equipmentReady': plan.equipment_ready,
        'notes': plan.notes or None,
    }


def serialize_performance(review):
    return {
        'id': str(review.id),
        'employeeName': review.employee_name,
        'reviewCycle': review.review_cycle,
        'owner': review.owner,
        'priority': review.priority,
        'status': review.status,
        'notes': review.notes or None,
    }


def serialize_learning(program):
    return {
        'id': str(program.id),
        'programName': program.program_name,
        'audience': program.audience,
        'owner': program.owner,
        'status': program.status,
        'priority': program.priority,
        'notes': program.notes or None,
    }


def serialize_offboarding(plan):
    return {
        'id': str(plan.id),
        'employeeName': plan.employee_name,
        'lastWorkingDay': plan.last_working_day.isoformat(),
        'owner': plan.owner,
        'status': plan.status,
        'assetsCleared': plan.assets_cleared,
        'notes': plan.notes or None,
    }
