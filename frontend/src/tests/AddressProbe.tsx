import { useLocation, useNavigate } from 'react-router-dom';

// What the address bar would show, for a test to read, and the browser's own
// Back button, for a test to press. Neither is part of the screen.
function AddressProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="address" hidden>
        {location.pathname + location.search}
      </output>
      <button type="button" data-testid="browser-back" hidden onClick={() => navigate(-1)} />
    </>
  );
}

export default AddressProbe;
