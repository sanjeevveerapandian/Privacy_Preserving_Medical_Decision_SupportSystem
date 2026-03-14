from fastapi import APIRouter, HTTPException, Depends, Request
from backend.utils.file_handler import load_users, save_users
from datetime import datetime
import copy

router = APIRouter(prefix="/auth", tags=["Auth"])

def get_all_users():
    """Get all users including admin"""
    users = load_users()
    # Convert to list format for easier frontend handling
    user_list = []
    for username, data in users.items():
        user_data = data.copy()
        user_data["username"] = username
        user_list.append(user_data)
    return user_list

def get_user_by_username(username: str):
    users = load_users()
    if username in users:
        user_data = users[username].copy()
        user_data["username"] = username
        return user_data
    return None

@router.get("/users/all")
def get_all_users_route():
    """Get all users"""
    users = get_all_users()
    return {"users": users}

@router.get("/users/{username}")
def get_user(username: str):
    """Get specific user details"""
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": user}

@router.post("/register")
def register_user(username: str, password: str, role: str = "patient", email: str = "", full_name: str = ""):
    users = load_users()
    if username in users:
        raise HTTPException(status_code=400, detail="Username already exists.")
    
    users[username] = {
        "username": username,
        "password": password,
        "role": role,
        "email": email,
        "full_name": full_name,
        "approved": False,
        "status": "active",
        "registered_at": datetime.now().isoformat(),
        "last_login": None,
        "updated_at": datetime.now().isoformat()
    }
    save_users(users)
    return {
        "message": f"User '{username}' registered successfully. Pending admin approval.",
        "success": True
    }

@router.post("/login")
def login_user(username: str, password: str):
    users = load_users()
    user = users.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not user["approved"]:
        raise HTTPException(status_code=403, detail="Account not approved yet.")
    
    # Update last login
    users[username]["last_login"] = datetime.now().isoformat()
    save_users(users)
    
    return {
        "username": username, 
        "role": user["role"], 
        "approved": user["approved"],
        "full_name": user.get("full_name", ""),
        "email": user.get("email", "")
    }



@router.put("/admin/update/{username}")
def update_user(username: str, role: str = None, email: str = None, 
                full_name: str = None, status: str = None, approved: bool = None):
    users = load_users()
    
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Don't allow modifying admin user except by admin
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot modify admin user.")
    
    user = users[username]
    
    # Update fields if provided
    if role is not None:
        user["role"] = role
    if email is not None:
        user["email"] = email
    if full_name is not None:
        user["full_name"] = full_name
    if status is not None:
        user["status"] = status
    if approved is not None:
        user["approved"] = approved
    
    user["updated_at"] = datetime.now().isoformat()
    
    save_users(users)
    
    return {
        "message": f"User '{username}' updated successfully.",
        "success": True,
        "user": user
    }

@router.delete("/admin/delete/{username}")
def delete_user(username: str):
    users = load_users()
    
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found.")
    
    # Don't allow deleting admin
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user.")
    
    # Store user data before deletion for response
    deleted_user = users[username].copy()
    deleted_user["username"] = username
    
    del users[username]
    save_users(users)
    
    return {
        "message": f"User '{username}' deleted successfully.",
        "success": True,
        "deleted_user": deleted_user
    }

@router.post("/admin/reset-password/{username}")
def reset_password(username: str, new_password: str):
    users = load_users()
    
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found.")
    
    users[username]["password"] = new_password
    users[username]["updated_at"] = datetime.now().isoformat()
    
    save_users(users)
    
    return {
        "message": f"Password for '{username}' reset successfully.",
        "success": True
    }

@router.get("/admin/stats")
def get_user_stats():
    users = load_users()
    
    stats = {
        "total_patients": 0,
        "total_doctors": 0,
        "total_researchers": 0,
        "pending_users": 0,
        "approved_users": 0,
        "active_users": 0,
        "inactive_users": 0,
        "total_users": len(users)
    }
    
    for user in users.values():
        role = user["role"]
        if role == "patient":
            stats["total_patients"] += 1
        elif role == "doctor":
            stats["total_doctors"] += 1
        elif role == "researcher":
            stats["total_researchers"] += 1
        
        if user["approved"]:
            stats["approved_users"] += 1
        else:
            stats["pending_users"] += 1
        
        if user.get("status") == "active":
            stats["active_users"] += 1
        elif user.get("status") == "inactive":
            stats["inactive_users"] += 1
    
    return stats

@router.get("/admin/pending")
def get_pending_users():
    users = load_users()
    
    pending_users = []
    for username, user_data in users.items():
        if not user_data["approved"] and username != "admin":
            pending_users.append({
                "username": username,
                "role": user_data["role"],
                "email": user_data.get("email", ""),
                "full_name": user_data.get("full_name", ""),
                "registered_at": user_data.get("registered_at", "N/A"),
                "status": user_data.get("status", "pending")
            })
    
    return {"pending_users": pending_users}

@router.post("/admin/approve/{username}")
def approve_user(username: str):
    return update_user(username, approved=True)

@router.post("/admin/reject/{username}")
def reject_user(username: str):
    return delete_user(username)