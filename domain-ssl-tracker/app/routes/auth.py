from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import check_credentials, make_session_cookie, is_logged_in, SESSION_COOKIE

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/", error: str = ""):
    if is_logged_in(request):
        return RedirectResponse(url=next, status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "next": next,
        "error": error,
    })


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
):
    if check_credentials(username, password):
        response = RedirectResponse(url=next or "/", status_code=303)
        response.set_cookie(
            key=SESSION_COOKIE,
            value=make_session_cookie(),
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 days
        )
        return response

    return templates.TemplateResponse("login.html", {
        "request": request,
        "next": next,
        "error": "Invalid username or password.",
    }, status_code=401)


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response
