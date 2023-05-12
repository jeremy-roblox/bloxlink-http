import fastapi


bloxlink = None


print("registering endpoints")
subapp = fastapi.FastAPI()

@subapp.get("/")
async def test():
    me = await bloxlink.rest.fetch_my_user()
    return {"message": "hey"}


def register_endpoints(app, bot):
    global bloxlink

    bloxlink = bot

    app.mount("/test", subapp)