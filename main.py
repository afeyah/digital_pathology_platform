from nicegui import ui
# THIS IMPORT IS REQUIRED so that the decorators inside these files are executed
from app.pages import login_page, dashboard_page, viewer_page, report_page

# Main page (Index) - Usually redirects to the Login page
@ui.page('/')
def index():
    ui.navigate.to('/login')


ui.run(title="Digital Pathology Platform", port=8080)
