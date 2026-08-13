def serialize_s3_config(config):
    """Never returns the secret key; the frontend can only tell whether one
    is stored, not what it is."""
    access_key = config.access_key_id or ''
    return {
        'bucketName': config.bucket_name,
        'region': config.region,
        'endpointUrl': config.endpoint_url,
        'accessKeyIdLast4': access_key[-4:] if len(access_key) >= 4 else '',
        'hasAccessKey': bool(config.access_key_id),
        'hasSecretKey': bool(config.secret_access_key_encrypted),
        'defaultVisibility': config.default_visibility,
        'isActive': config.is_active,
        'updatedAt': config.updated_at.isoformat(),
    }
