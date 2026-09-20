import React from "react";
import { BrowserRouter, Routes, Route, useSearchParams } from "react-router-dom";
import { Toaster } from "sonner";
import "./dueo.css";
import "./pages/Landing.css";

import Landing from "./pages/Landing";
import Invite from "./pages/Invite";
import InviteConsume from "./pages/InviteConsume";
import Login from "./pages/Login";
import Setup from "./pages/Setup";
import Today from "./pages/Today";
import AdminLeads from "./pages/AdminLeads";
import AdminUsers from "./pages/AdminUsers";
import AdminOutbox from "./pages/AdminOutbox";

function InviteRoute() {
  const [params] = useSearchParams();
  return params.get("token") ? <InviteConsume /> : <Invite />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-center" richColors />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/invite" element={<InviteRoute />} />
        <Route path="/login" element={<Login />} />
        <Route path="/setup" element={<Setup />} />
        <Route path="/today" element={<Today />} />
        <Route path="/admin/leads" element={<AdminLeads />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/outbox" element={<AdminOutbox />} />
      </Routes>
    </BrowserRouter>
  );
}
