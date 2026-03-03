# Custom NetBox image with topology-views and custom-objects plugins
# Built automatically by docker-compose.netbox.yml
FROM netboxcommunity/netbox:v4.4

USER root

# Bootstrap pip into the venv (base image ships without pip/ensurepip)
COPY plugin_requirements.txt /opt/netbox/
RUN curl -sSL https://bootstrap.pypa.io/get-pip.py | /opt/netbox/venv/bin/python && \
    /opt/netbox/venv/bin/pip install --no-cache-dir -r /opt/netbox/plugin_requirements.txt

# Fix: The Docker build tag (e.g. "Docker-3.2.1") makes settings.VERSION
# non-PEP-440 compliant, which crashes netbox-topology-views on import.
# Remove the build field so VERSION stays PEP-440 compliant.
RUN sed -i '/^build:/d' /opt/netbox/netbox/local/release.yaml

# Add plugin configuration (must be before collectstatic)
COPY plugins.py /etc/netbox/config/plugins.py

# Copy plugin static files directly (collectstatic needs DB during build)
# netbox_custom_objects may not ship static files — copy only if present
RUN cp -r /opt/netbox/venv/lib/python3.12/site-packages/netbox_topology_views/static/netbox_topology_views \
    /opt/netbox/netbox/static/netbox_topology_views && \
    if [ -d /opt/netbox/venv/lib/python3.12/site-packages/netbox_custom_objects/static/netbox_custom_objects ]; then \
        cp -r /opt/netbox/venv/lib/python3.12/site-packages/netbox_custom_objects/static/netbox_custom_objects \
        /opt/netbox/netbox/static/netbox_custom_objects; \
    fi

USER unit:unit
