"""Same-ChatGPT-Project messaging over the existing Atlas RDC bus domain.

Atlas Bus v1 currently has platform project domains atlas/rdc/bandmates/
presentation. Real ChatGPT project IDs are an *additional* membership scope,
verified here before passing a recipient to the RDC bus. Never expose the
raw BusStore to model-request arguments; direct access could bypass this
project-subtenant check. Production requires authenticated session enrollment
and independent Atlas owner acceptance.
"""
from __future__ import annotations

from .chat_interconnect import ChatClient, ChatError
from .chat_rooms import ChatRoom


class ProjectMessageDenied(ValueError):
    """No verified sender, target or active same-project chat grant."""


class ProjectScopedChatMessenger:
    """One restricted ChatGPT-to-ChatGPT tool adapter.

    session_verifier may only resolve trusted host-bound opaque references,
    never a project/session string supplied by the model. grant_store holds
    the project-wide, one-time activated 'message' capability.
    """

    def __init__(self,bus,*,session_verifier,grant_store):
        self.bus=bus
        self.verifier=session_verifier
        self.grants=grant_store

    def _actor(self,handle):
        identity=self.verifier.verify_actor(handle)
        if (not isinstance(identity,dict) or identity.get("authenticated") is not True
                or identity.get("provider") != "chatgpt"
                or not isinstance(identity.get("project_id"),str)
                or not isinstance(identity.get("session_id"),str)):
            raise ProjectMessageDenied("ChatGPT MCP tool identity is not host-authenticated.")
        if not self.grants.allowed(identity["project_id"],"message"):
            raise ProjectMessageDenied("Project has no active messaging grant.")
        return identity

    def _target(self,handle,project):
        identity=self.verifier.verify_target(handle)
        if (not isinstance(identity,dict) or identity.get("verified") is not True
                or identity.get("provider")!="chatgpt"
                or identity.get("project_id")!=project
                or not isinstance(identity.get("session_id"),str)):
            raise ProjectMessageDenied("Peer has no verified membership in the same ChatGPT project.")
        return identity["session_id"]

    def send(self,source_handle,target_handle,text,*,key):
        source=self._actor(source_handle)
        target=self._target(target_handle,source["project_id"])
        return ChatClient(self.bus,source["session_id"],project="rdc").send(target,text,key=key)

    def claim(self,source_handle,*,holder):
        source=self._actor(source_handle)
        return ChatClient(self.bus,source["session_id"],project="rdc").claim(holder=holder)

    def mark_fetched(self,source_handle,claim,*,holder):
        source=self._actor(source_handle)
        return ChatClient(self.bus,source["session_id"],project="rdc").mark_fetched(claim,holder=holder)

    def ack(self,source_handle,message_id):
        source=self._actor(source_handle)
        return ChatClient(self.bus,source["session_id"],project="rdc").ack(message_id)

    def reply(self,source_handle,target_handle,text,*,key,parent_id):
        source=self._actor(source_handle)
        target=self._target(target_handle,source["project_id"])
        return ChatClient(self.bus,source["session_id"],project="rdc").send(
            target,text,key=key,reply_to=parent_id)

    def broadcast(self,source_handle,members,text,*,key,room_key,parent_id=None):
        source=self._actor(source_handle)
        if not isinstance(members,(list,tuple,set,frozenset)):
            raise ProjectMessageDenied("Exact two or three project participant handles required.")
        peers=tuple(self._target(item,source["project_id"]) for item in members)
        room=ChatRoom(self.bus,source["session_id"],peers,
                      room_key=room_key)
        return room.broadcast(text,key=key,parent_id=parent_id)
