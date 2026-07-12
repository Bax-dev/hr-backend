def serialize_department(department, head_count=0):
    return {
        'id': department.id,
        'name': department.name,
        'headCount': head_count,
        'manager': department.manager,
        'color': department.color,
    }
