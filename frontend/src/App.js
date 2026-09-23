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
import Upload from "./pages/Upload";
import Review from "./pages/Review";
import Preview from "./pages/Preview";
import Proceed from "./pages/Proceed";
import Contacts from "./pages/Contacts";
import Tone from "./pages/Tone";
import PublicHub from "./pages/PublicHub";
import Dashboard from "./pages/Dashboard";
import HubDetail from "./pages/HubDetail";
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
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/hub/:id/detail" element={<HubDetail />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/hub/:id/review" element={<Review />} />
        <Route path="/hub/:id/preview" element={<Preview />} />
        <Route path="/hub/:id/proceed" element={<Proceed />} />
        <Route path="/hub/:id/contacts" element={<Contacts />} />
        <Route path="/hub/:id/tone" element={<Tone />} />
        <Route path="/hub/:token" element={<PublicHub />} />
        <Route path="/admin/leads" element={<AdminLeads />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/outbox" element={<AdminOutbox />} />
      </Routes>
    </BrowserRouter>
  );
}
