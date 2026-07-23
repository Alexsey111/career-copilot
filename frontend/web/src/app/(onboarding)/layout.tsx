import type { Metadata } from "next";
import OnboardingClientLayout from "./OnboardingClientLayout";

export const metadata: Metadata = {
  title: "Согласия — AI Career Copilot",
};

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <OnboardingClientLayout>{children}</OnboardingClientLayout>;
}
