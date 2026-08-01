-- The current analytical source labels are already correctly formatted.
-- Keep the override framework, but remove corrections that are no longer
-- necessary.

DELETE FROM analytics.dim_display_label_override
WHERE
    (entity_type = 'county'
     AND entity_key IN ('38079', '46102'))

    OR

    (entity_type = 'cause'
     AND entity_key IN ('441', '976'));


ANALYZE analytics.dim_display_label_override;