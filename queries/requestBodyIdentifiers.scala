import scala.collection.mutable

def loadParams(path: String): Map[String, Seq[String]] = {
  val decoder = java.util.Base64.getDecoder
  val source = scala.io.Source.fromFile(path)
  try {
    source.getLines().map(_.trim).filter(_.nonEmpty).toList.flatMap { line =>
      val tab = line.indexOf('\t')
      if (tab < 0) None
      else {
        val key = line.substring(0, tab)
        val value = new String(decoder.decode(line.substring(tab + 1)), "UTF-8")
        Some((key, value))
      }
    }.groupBy(_._1).map { case (k, kvs) => (k, kvs.map(_._2)) }
  } finally source.close()
}

def findRequestBodyIdentifiers(
    paramsPath: String,
    outputPath: String
): Unit = {
  val params = loadParams(paramsPath)
  val identifierNames = params.getOrElse("identifier", Nil).toSet
  val bodyAnnotations = params.getOrElse("bodyAnnotation", Nil).toSet
  val matchGenericId = params.getOrElse("matchGenericId", Nil).headOption.contains("true")
  val endpoints = params.getOrElse("endpoint", Nil).toList

  def esc(s: String): String =
    if (s == null) ""
    else s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r")

  def norm(s: String): String = s.toLowerCase.replaceAll("[^a-z0-9]", "")
  val normIds = identifierNames.map(norm).filter(_.nonEmpty)
  // A bare `id` or a `*Id` suffix
  def isGenericId(name: String): Boolean = {
    val n = if (name == null) "" else name
    n == "id" || n == "ID" || n.endsWith("Id") || n.endsWith("_id")
  }
  def matchesId(name: String): Boolean = {
    val x = norm(name)
    (x.nonEmpty && normIds.exists(id => x == id || x.endsWith(id))) ||
      (matchGenericId && isGenericId(name))
  }
  def fieldFromAccessor(n: String): String =
    if (n.startsWith("get")) n.drop(3) else if (n.startsWith("is")) n.drop(2) else n

  // type fullName -> accessor method names called on it
  val accessorByType = mutable.Map[String, mutable.Set[String]]()
  cpg.call.methodFullName(".*\\.(get|is)[A-Z].*").foreach { c =>
    val mfn = c.methodFullName
    if (mfn != null) {
      val beforeColon = mfn.split(":").head
      val idx = beforeColon.lastIndexOf('.')
      if (idx > 0) {
        val typ = beforeColon.substring(0, idx)
        val meth = beforeColon.substring(idx + 1)
        accessorByType.getOrElseUpdate(typ, mutable.Set[String]()) += meth
      }
    }
  }

  val bodyAnnoSeq = bodyAnnotations.toSeq
  val results = mutable.ArrayBuffer[String]()

  for (ep <- endpoints) {
    try {
      cpg.method.fullNameExact(ep).headOption.foreach { method =>
        val bodyParams =
          if (bodyAnnoSeq.isEmpty) Nil
          else method.parameter.where(_.annotation.name(bodyAnnoSeq: _*)).l

        val matched = mutable.LinkedHashMap[String, String]()
        for (param <- bodyParams) {
          val t = param.typeFullName
          if (t != null && t.nonEmpty && t != "ANY" && t != "java.lang.Object") {
            val td = cpg.typeDecl.fullNameExact(t)
            val memberNames = td.member.name.l
            val getterFields = td.method.name.l
              .filter(n => n.startsWith("get") || n.startsWith("is"))
              .map(fieldFromAccessor)
            val callFields =
              accessorByType.get(t).map(_.toList.map(fieldFromAccessor)).getOrElse(Nil)

            for (field <- (memberNames ++ getterFields ++ callFields).distinct) {
              if (matchesId(field) && !matched.contains(field)) {
                matched.put(field, t)
              }
            }
          }
        }

        matched.headOption.foreach { case (field, modelType) =>
          results.append(
            s"""{"endpoint":"${esc(ep)}","field":"${esc(field)}","modelType":"${esc(modelType)}"}"""
          )
        }
      }
    } catch {
      case e: Exception => println(s"[reqbody] error for $ep: ${e.getMessage}")
    }
  }

  val writer = new java.io.PrintWriter(new java.io.File(outputPath))
  try { writer.write(results.mkString("[", ",", "]")) } finally { writer.close() }
}
