<?php
session_start();

// Hardcoded user (for demo purposes)
$correct_username = "admin";

// This is a hashed version of the password "engilab123"
$hashed_password = '$2y$10$wHk8R4Rj6WQkZ3xY6z5H6uG6k9zT5R7Z2FzH2R5y9l3XjJ8kP9YwG';

if ($_SERVER["REQUEST_METHOD"] == "POST") {

    $username = $_POST['uname'];
    $password = $_POST['psw'];

    if ($username === $correct_username && password_verify($password, $hashed_password)) {
        
        $_SESSION['user'] = $username;
        
        echo "<h2>Login successful!</h2>";
        echo "<p>Welcome, " . htmlspecialchars($username) . ".</p>";
        echo "<a href='index.html'>Go back</a>";

    } else {
        echo "<h2>Invalid username or password.</h2>";
        echo "<a href='index.html'>Try again</a>";
    }

} else {
    echo "Invalid request.";
}
?>
