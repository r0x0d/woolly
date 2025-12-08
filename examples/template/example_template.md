 Report for {{ root_package }}

Generated: {{ timestamp }}
Language: {{ language }}

## Summary
- Total: {{ total_dependencies }}
- Packaged: {{ packaged_count }}
- Missing: {{ missing_count }}

{% if missing_packages %}
## Missing Packages
{% for pkg in missing_packages %}
- {{ pkg }}
{% endfor %}
{% endif %}