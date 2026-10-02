"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const user = getUser();
    if (!user || user.role !== "admin") router.replace("/login");
    else router.replace("/admin");
  }, [router]);
  return null;
}
