import asyncio


class APIService:
    async def _handle_response(self, success: bool, data=None, error_msg=""):
        # Single logic to handle all API responses
        if success:
            return {"success": True, "data": data}
        return {"success": False, "error": error_msg}

    async def login(self, username, password):
        # Simulate network delay so that loading spinner is visible
        await asyncio.sleep(1.5)

        # Mock credentials for prototype
        if username == "admin" and password == "password123":
            return await self._handle_response(
                True, data={"name": "Dr. Ahmad", "id": "P-001"}
            )
        return await self._handle_response(
            False, error_msg="Incorrect username or password!"
        )


# Singleton instance to be imported anywhere
api = APIService()
