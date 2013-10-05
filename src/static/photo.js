
function set_average_stars(avg) {
  var stars = 0;
  while (avg > 0) {
    if (avg > 0.9) {
      set_average_star(stars, "red");
      stars++;
      avg -= 1.0;
    } else if (avg > 0.1) {
      set_average_star(stars, "half-red");
      stars++;
      avg = 0;
    } else
      avg = 0;
  } 
  for (; stars < 5; stars++) {
    set_average_star(stars, "gray");
  }
}
function set_average_star(ix, color) {
  img = document.getElementById("avgstar" + ix);
  img.src = "static/" + color + "-star.png"; 
}

function setstars(start, end, type) {
  for (var ix = start; ix <= end; ix++) {
    img = document.getElementById("star" + ix);
    img.src = "static/" + type + "-star.png";
  }
}
function moveonto(number) {
  setstars(1, number, "yellow");
  setstars(number + 1, 5, "white");
}
function moveoff(number) {
  setstars(1, userscore, "yellow");
  setstars(userscore + 1, 5, "white");
}
function vote(number) {
  var xmlhttp = new XMLHttpRequest();
  xmlhttp.open("POST", "set-score?id=" + photoid + "&score=" + number, false);
  xmlhttp.send("");
  if (xmlhttp.readyState == 4 &&
      xmlhttp.status == 200) {
    if (userscore == 0) {
      average = ((average * votes) + number) / (votes + 1);
      votes = votes + 1;
      userscore = number;
    } else {
      average = ((average * votes) + number - userscore) / votes;
      userscore = number;
    }
    set_average_stars(average);
  } else {
    alert("Problem: " + xmlhttp.readyState + ", " + xmlhttp.status);
  }
}
