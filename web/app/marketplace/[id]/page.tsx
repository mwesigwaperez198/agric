import ListingDetailView from "./view";

export function generateStaticParams() {
  return [{ id: "1" }, { id: "2" }];
}

export const dynamicParams = false;

export default function ListingDetailPage() {
  return <ListingDetailView />;
}
