-- generated: the middle tier for Clients, with the reviewer's duplicate merges applied
{{ config(alias='Clients') }}
SELECT
    s.client_id,
    s.company_name,
    s.industry,
    s.website,
    s.phone,
    s.address_line_1,
    s.address_line_2,
    s.city,
    s.postcode,
    s.country,
    s.status,
    s.owner_user_id,
    s.created_at
FROM {{ ref('stg_clients') }} s
WHERE s.client_id NOT IN (SELECT duplicate FROM {{ ref('merges') }} WHERE kind = 'client')
