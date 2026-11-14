import { Suspense } from "react";
import Launcher from "./Launcher";

export default function Page() {
  return (
    <Suspense>
      <Launcher />
    </Suspense>
  );
}
