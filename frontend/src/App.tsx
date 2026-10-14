import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { HomeScreen } from "./screens/HomeScreen";
import { ReviewScreen } from "./screens/ReviewScreen";

export function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomeScreen />} />
          <Route path="/documents/:id" element={<ReviewScreen />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
