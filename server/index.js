const express = require('express')
const path = require('path')
const app = express()
const PORT = process.env.PORT || 3000

// Serve the built React files
app.use(express.static(path.join(__dirname, '..', 'client', 'dist')))

// API example
app.get('/api/hello', (req, res) => {
  res.json({ message: 'Hello from server!' })
})

// For any other route, return the React index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'client', 'dist', 'index.html'))
})

app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`)
})
